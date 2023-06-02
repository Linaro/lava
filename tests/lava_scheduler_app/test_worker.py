# Copyright (C) 2020 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from lava_common.version import __version__
from lava_common.yaml import yaml_safe_load
from lava_results_app.models import TestCase
from lava_scheduler_app.models import Device, DeviceType, TestJob, Worker


def create_objects(w):
    # Add jobs and test again
    user = User.objects.create(username="submitter")
    qemu = DeviceType.objects.create(name="qemu")
    qemu01 = Device.objects.create(
        hostname="qemu01",
        device_type=qemu,
        health=Device.HEALTH_GOOD,
        state=Device.STATE_RUNNING,
        worker_host=w,
    )
    qemu02 = Device.objects.create(
        hostname="qemu02",
        device_type=qemu,
        health=Device.HEALTH_GOOD,
        state=Device.STATE_RUNNING,
        worker_host=w,
    )
    qemu03 = Device.objects.create(
        hostname="qemu03",
        device_type=qemu,
        health=Device.HEALTH_GOOD,
        state=Device.STATE_RUNNING,
        worker_host=w,
    )
    qemu04 = Device.objects.create(
        hostname="qemu04",
        device_type=qemu,
        health=Device.HEALTH_GOOD,
        state=Device.STATE_RUNNING,
        worker_host=Worker.objects.create(hostname="worker-02"),
    )
    qemu05 = Device.objects.create(
        hostname="qemu05",
        device_type=qemu,
        health=Device.HEALTH_GOOD,
        state=Device.STATE_RUNNING,
        worker_host=w,
    )
    j1 = TestJob.objects.create(
        definition="device_type: qemu",
        requested_device_type=qemu,
        actual_device=qemu01,
        state=TestJob.STATE_SCHEDULED,
        submitter=user,
    )
    j2 = TestJob.objects.create(
        definition="device_type: qemu",
        requested_device_type=qemu,
        actual_device=qemu02,
        state=TestJob.STATE_RUNNING,
        submitter=user,
    )
    j3 = TestJob.objects.create(
        definition="device_type: qemu",
        requested_device_type=qemu,
        actual_device=qemu03,
        state=TestJob.STATE_CANCELING,
        submitter=user,
    )
    j4 = TestJob.objects.create(
        definition="device_type: qemu",
        requested_device_type=qemu,
        actual_device=qemu04,
        state=TestJob.STATE_CANCELING,
        submitter=user,
    )
    j5 = TestJob.objects.create(
        definition="protocols:\n  lava-multinode:\n    role: hello",
        requested_device_type=qemu,
        actual_device=qemu05,
        target_group="1234",
        state=TestJob.STATE_SCHEDULED,
        submitter=user,
    )
    j6 = TestJob.objects.create(
        definition="connection: ssh\nhost_role: hello",
        target_group="1234",
        state=TestJob.STATE_SCHEDULED,
        submitter=user,
    )
    j5.sub_id = f"{j5.id}.0"
    j6.sub_id = f"{j5.id}.1"
    j5.save()
    j6.save()

    return {
        "device-type": qemu,
        "devices": [qemu01, qemu02, qemu03, qemu04, qemu05],
        "jobs": [j1, j2, j3, j4, j5, j6],
    }


@pytest.mark.django_db
def test_internal_v1_jobs_get(client, mocker, settings):
    # Create objects
    objs = create_objects(Worker.objects.create(hostname="worker-01"))
    (j1, j2, j3, j4, j5, j6) = objs["jobs"]

    # Test errors
    ret = client.get(reverse("lava.scheduler.internal.v1.jobs", args=["12345"]))
    assert ret.status_code == 404

    ret = client.get(reverse("lava.scheduler.internal.v1.jobs", args=[j1.id]))
    assert ret.status_code == 400
    assert ret.json()["error"] == "Missing 'token'"

    ret = client.get(
        reverse("lava.scheduler.internal.v1.jobs", args=[j1.id]), HTTP_LAVA_TOKEN=""
    )
    assert ret.status_code == 400
    assert ret.json()["error"] == "Invalid 'token'"

    ret = client.get(
        reverse("lava.scheduler.internal.v1.jobs", args=[j1.id]),
        HTTP_LAVA_TOKEN=j1.token,
    )
    assert ret.status_code == 200
    assert list(ret.json().keys()) == [
        "definition",
        "device",
        "dispatcher",
        "env",
        "env-dut",
    ]
    print(ret.json())
    assert yaml_safe_load(ret.json()["definition"]) == {
        "compatibility": 0,
        "device_type": "qemu",
    }
    assert "hostname: qemu05" not in ret.json()["device"]
    assert "available_architectures:" in ret.json()["device"]

    ret = client.get(
        reverse("lava.scheduler.internal.v1.jobs", args=[j6.id]),
        HTTP_LAVA_TOKEN=j6.token,
    )
    assert ret.status_code == 200
    assert list(ret.json().keys()) == [
        "definition",
        "device",
        "dispatcher",
        "env",
        "env-dut",
    ]
    assert yaml_safe_load(ret.json()["definition"]) == {
        "compatibility": 0,
        "connection": "ssh",
        "host_role": "hello",
    }
    assert "hostname: qemu05" in ret.json()["device"]
    assert "available_architectures:" not in ret.json()["device"]


@pytest.mark.django_db
def test_internal_v1_jobs_post(client, mocker, settings):
    # Create objects
    objs = create_objects(Worker.objects.create(hostname="worker-01"))
    (j1, j2, j3, j4, j5, j6) = objs["jobs"]

    # Test errors
    ret = client.post(reverse("lava.scheduler.internal.v1.jobs", args=["12345"]))
    assert ret.status_code == 404

    ret = client.post(reverse("lava.scheduler.internal.v1.jobs", args=[j1.id]))
    assert ret.status_code == 400
    assert ret.json()["error"] == "Missing 'token'"

    ret = client.post(
        reverse("lava.scheduler.internal.v1.jobs", args=[j1.id]), HTTP_LAVA_TOKEN=""
    )
    assert ret.status_code == 400
    assert ret.json()["error"] == "Invalid 'token'"

    ret = client.post(
        reverse("lava.scheduler.internal.v1.jobs", args=[j1.id]),
        HTTP_LAVA_TOKEN=j1.token,
    )
    assert ret.status_code == 400
    assert ret.json()["error"] == "Invalid state ''"

    ret = client.post(
        reverse("lava.scheduler.internal.v1.jobs", args=[j1.id]),
        HTTP_LAVA_TOKEN=j1.token,
        data={"state": "Canceling"},
    )
    assert ret.status_code == 400
    assert ret.json()["error"] == "Not handled state 'Canceling'"

    # Successful call
    ret = client.post(
        reverse("lava.scheduler.internal.v1.jobs", args=[j1.id]),
        HTTP_LAVA_TOKEN=j1.token,
        data={"state": "Running"},
    )
    assert ret.status_code == 200
    j1.refresh_from_db()
    assert j1.state == TestJob.STATE_RUNNING

    ret = client.post(
        reverse("lava.scheduler.internal.v1.jobs", args=[j1.id]),
        HTTP_LAVA_TOKEN=j1.token,
        data={"state": "Finished"},
    )
    assert ret.status_code == 400
    assert ret.json()["error"] == "Invalid health ''"

    ret = client.post(
        reverse("lava.scheduler.internal.v1.jobs", args=[j1.id]),
        HTTP_LAVA_TOKEN=j1.token,
        data={"state": "Finished", "result": "pass"},
    )
    assert ret.status_code == 200
    j1.refresh_from_db()
    assert j1.state == TestJob.STATE_FINISHED
    assert j1.health == TestJob.HEALTH_COMPLETE

    ret = client.post(
        reverse("lava.scheduler.internal.v1.jobs", args=[j2.id]),
        HTTP_LAVA_TOKEN=j2.token,
        data={
            "state": "Finished",
            "result": "fail",
            "error_type": "Bug",
            "errors": "an error",
        },
    )
    assert ret.status_code == 200
    j2.refresh_from_db()
    assert j2.state == TestJob.STATE_FINISHED
    assert j2.health == TestJob.HEALTH_INCOMPLETE
    assert j2.failure_comment == "an error"


@pytest.mark.django_db
def test_internal_v1_jobs_logs(client, mocker, settings):
    # Create objects
    objs = create_objects(Worker.objects.create(hostname="worker-01"))
    (j1, j2, j3, j4, j5, j6) = objs["jobs"]

    # Test errors
    ret = client.post(reverse("lava.scheduler.internal.v1.jobs.logs", args=["0"]))
    assert ret.status_code == 404

    ret = client.post(reverse("lava.scheduler.internal.v1.jobs.logs", args=[j1.id]))
    assert ret.status_code == 400
    assert ret.json()["error"] == "Missing 'token'"

    ret = client.post(
        reverse("lava.scheduler.internal.v1.jobs.logs", args=[j1.id]),
        HTTP_LAVA_TOKEN="",
    )
    assert ret.status_code == 400
    assert ret.json()["error"] == "Invalid 'token'"

    ret = client.post(
        reverse("lava.scheduler.internal.v1.jobs.logs", args=[j1.id]),
        HTTP_LAVA_TOKEN=j1.token,
    )
    assert ret.status_code == 400
    assert ret.json()["error"] == "Missing 'lines'"

    ret = client.post(
        reverse("lava.scheduler.internal.v1.jobs.logs", args=[j1.id]),
        data={"lines": ["hello"]},
        HTTP_LAVA_TOKEN=j1.token,
    )
    assert ret.status_code == 400
    assert ret.json()["error"] == "Missing 'index'"

    ret = client.post(
        reverse("lava.scheduler.internal.v1.jobs.logs", args=[j1.id]),
        data={"index": "a", "lines": ["hello"]},
        HTTP_LAVA_TOKEN=j1.token,
    )
    assert ret.status_code == 400
    assert ret.json()["error"] == "Invalid 'index'"

    # Successes
    ret = client.post(
        reverse("lava.scheduler.internal.v1.jobs.logs", args=[j1.id]),
        data={
            "index": 0,
            "lines": '- {"lvl": "info", "msg": "hello world"}\n- {"lvl": "debug", "msg": "a debug message"}',
        },
        HTTP_LAVA_TOKEN=j1.token,
    )
    assert ret.status_code == 200
    assert ret.json() == {"line_count": 2}
    assert (
        (Path(j1.output_dir) / "output.yaml").read_text()
        == """- {"lvl": "info", "msg": "hello world"}
- {"lvl": "debug", "msg": "a debug message"}
"""
    )

    # Resend the exact same lines: nothing should change on the FS
    ret = client.post(
        reverse("lava.scheduler.internal.v1.jobs.logs", args=[j1.id]),
        data={
            "index": 0,
            "lines": '- {"lvl": "info", "msg": "hello world"}\n- {"lvl": "debug", "msg": "a debug message"}',
        },
        HTTP_LAVA_TOKEN=j1.token,
    )
    assert ret.status_code == 200
    assert ret.json() == {"line_count": 2}
    assert (
        (Path(j1.output_dir) / "output.yaml").read_text()
        == """- {"lvl": "info", "msg": "hello world"}
- {"lvl": "debug", "msg": "a debug message"}
"""
    )

    # Resend the same lines plus some new ones: only the new ones are added
    ret = client.post(
        reverse("lava.scheduler.internal.v1.jobs.logs", args=[j1.id]),
        data={
            "index": 1,
            "lines": '- {"lvl": "debug", "msg": "a debug message"}\n- {"lvl": "error", "msg": "an error!"}',
        },
        HTTP_LAVA_TOKEN=j1.token,
    )
    assert ret.status_code == 200
    assert ret.json() == {"line_count": 2}
    assert (
        (Path(j1.output_dir) / "output.yaml").read_text()
        == """- {"lvl": "info", "msg": "hello world"}
- {"lvl": "debug", "msg": "a debug message"}
- {"lvl": "error", "msg": "an error!"}
"""
    )

    # send only an event
    send_event = mocker.Mock()
    mocker.patch("lava_scheduler_app.views.send_event", send_event)

    ret = client.post(
        reverse("lava.scheduler.internal.v1.jobs.logs", args=[j1.id]),
        data={"index": 3, "lines": '- {"lvl": "event", "msg": "hello world"}'},
        HTTP_LAVA_TOKEN=j1.token,
    )
    assert ret.status_code == 200
    assert ret.json() == {"line_count": 1}
    assert (
        (Path(j1.output_dir) / "output.yaml").read_text()
        == """- {"lvl": "info", "msg": "hello world"}
- {"lvl": "debug", "msg": "a debug message"}
- {"lvl": "error", "msg": "an error!"}
- {"lvl": "debug", "msg": "hello world"}
"""
    )
    assert len(send_event.mock_calls) == 1
    assert send_event.mock_calls[0][1] == (
        ".event",
        "lavaserver",
        {"message": "hello world", "job": j1.id},
    )

    # send test cases
    ret = client.post(
        reverse("lava.scheduler.internal.v1.jobs.logs", args=[j1.id]),
        data={
            "index": 4,
            "lines": '- {"lvl": "results", "msg": {"case": "linux-posix-pwd", "definition": "0_smoke-tests", "endtc": 20, "result": "pass", "starttc": 10}}',
        },
        HTTP_LAVA_TOKEN=j1.token,
    )
    assert ret.status_code == 200
    assert ret.json() == {"line_count": 1}
    assert (
        (Path(j1.output_dir) / "output.yaml").read_text()
        == """- {"lvl": "info", "msg": "hello world"}
- {"lvl": "debug", "msg": "a debug message"}
- {"lvl": "error", "msg": "an error!"}
- {"lvl": "debug", "msg": "hello world"}
- {"lvl": "results", "msg": {"case": "linux-posix-pwd", "definition": "0_smoke-tests", "endtc": 20, "result": "pass", "starttc": 10}}
"""
    )

    assert TestCase.objects.count() == 1
    tc = TestCase.objects.all()[0]
    assert tc.name == "linux-posix-pwd"
    assert tc.result == TestCase.RESULT_PASS
    assert tc.start_log_line == 10
    assert tc.end_log_line == 20
    assert tc.suite.job == j1
    assert tc.suite.name == "0_smoke-tests"


@pytest.mark.django_db
def test_internal_v1_workers_get(client, mocker, settings):
    # Setup
    now = timezone.now()
    mocker.patch("django.utils.timezone.now", return_value=now)

    Worker.objects.create(
        hostname="worker-01", health=Worker.HEALTH_ACTIVE, state=Worker.STATE_OFFLINE
    )
    token = Worker.objects.get(hostname="worker-01").token

    # Test errors
    ret = client.get(reverse("lava.scheduler.internal.v1.workers"))
    assert ret.status_code == 404

    ret = client.get(reverse("lava.scheduler.internal.v1.workers", args=["worker-01"]))
    assert ret.status_code == 400
    assert ret.json()["error"] == "Missing 'token'"

    ret = client.get(
        reverse("lava.scheduler.internal.v1.workers", args=["worker-01"]),
        HTTP_LAVA_TOKEN="",
    )
    assert ret.status_code == 400
    assert ret.json()["error"] == "Invalid 'token'"

    ret = client.get(
        reverse("lava.scheduler.internal.v1.workers", args=["worker-01"]),
        HTTP_LAVA_TOKEN=token,
    )
    assert ret.status_code == 400
    assert ret.json()["error"] == "Missing 'version'"

    settings.ALLOW_VERSION_MISMATCH = True
    ret = client.get(
        reverse("lava.scheduler.internal.v1.workers", args=["worker-01"]),
        {"version": "v0.1"},
        HTTP_LAVA_TOKEN=token,
    )
    assert ret.status_code == 200

    settings.ALLOW_VERSION_MISMATCH = False
    ret = client.get(
        reverse("lava.scheduler.internal.v1.workers", args=["worker-01"]),
        {"version": "v0.1"},
        HTTP_LAVA_TOKEN=token,
    )
    assert ret.status_code == 409
    assert ret.json()["error"] == f"Version mismatch 'v0.1' vs '{__version__}'"

    # Test the working case without any jobs
    ret = client.get(
        reverse("lava.scheduler.internal.v1.workers", args=["worker-01"]),
        {"version": __version__},
        HTTP_LAVA_TOKEN=token,
    )
    assert ret.status_code == 200
    assert ret.json() == {"cancel": [], "running": [], "start": []}

    w = Worker.objects.get(hostname="worker-01")
    assert w.last_ping == now
    assert w.state == Worker.STATE_ONLINE

    # Add jobs and test again
    objs = create_objects(w)
    (j1, j2, j3, j4, j5, j6) = objs["jobs"]

    ret = client.get(
        reverse("lava.scheduler.internal.v1.workers", args=["worker-01"]),
        {"version": __version__},
        HTTP_LAVA_TOKEN=token,
    )
    assert ret.status_code == 200
    data = ret.json()
    assert sorted(data.keys()) == ["cancel", "running", "start"]
    assert data["cancel"] == [{"id": j3.id, "token": j3.token}]
    assert data["running"] == [{"id": j2.id, "token": j2.token}]
    assert len(data["start"]) == 3
    assert {"id": j1.id, "token": j1.token} in data["start"]
    assert {"id": j5.id, "token": j5.token} in data["start"]
    assert {"id": j6.id, "token": j6.token} in data["start"]


@pytest.mark.django_db
def test_internal_v1_workers_post(client, mocker, settings):
    ret = client.post(reverse("lava.scheduler.internal.v1.workers", args=["worker-01"]))
    assert ret.status_code == 403
    assert ret.json()["error"] == "POST is forbidden for such url"

    settings.WORKER_AUTO_REGISTER = False
    ret = client.post(reverse("lava.scheduler.internal.v1.workers"))
    assert ret.status_code == 403
    assert ret.json()["error"] == "Auto registration is disabled"

    settings.WORKER_AUTO_REGISTER = True
    ret = client.post(reverse("lava.scheduler.internal.v1.workers"), data={})
    assert ret.status_code == 400
    assert ret.json()["error"] == "Missing 'name'"

    mocker.patch("lava_scheduler_app.views.get_user_ip", mocker.Mock(return_value=None))
    ret = client.post(
        reverse("lava.scheduler.internal.v1.workers"), data={"name": "worker-01"}
    )
    assert ret.status_code == 400
    assert ret.json()["error"] == "Missing client ip"

    settings.WORKER_AUTO_REGISTER_NETMASK = ["192.168.0.0/24"]
    mocker.patch(
        "lava_scheduler_app.views.get_user_ip", mocker.Mock(return_value="192.168.1.10")
    )
    ret = client.post(
        reverse("lava.scheduler.internal.v1.workers"), data={"name": "worker-01"}
    )
    assert ret.status_code == 403
    assert ret.json()["error"] == "Auto registration is forbidden for '192.168.1.10'"

    settings.WORKER_AUTO_REGISTER_NETMASK = ["192.168.1.0/24"]
    mocker.patch(
        "lava_scheduler_app.views.get_user_ip", mocker.Mock(return_value="192.168.1.10")
    )
    ret = client.post(
        reverse("lava.scheduler.internal.v1.workers"), data={"name": "worker-01"}
    )
    assert ret.status_code == 200
    assert ret.json() == {
        "name": "worker-01",
        "token": Worker.objects.get(hostname="worker-01").token,
    }

    ret = client.post(
        reverse("lava.scheduler.internal.v1.workers"), data={"name": "worker-01"}
    )
    assert ret.status_code == 403
    assert ret.json()["error"] == "Worker 'worker-01' already registered"

    # Use username and password as simple user
    user = User.objects.create_user("simple-user", "user@example.com", "mypass")
    ret = client.post(
        reverse("lava.scheduler.internal.v1.workers"),
        data={"name": "worker-02", "username": "simple-user", "password": "wrong pass"},
    )
    assert ret.status_code == 403
    assert ret.json() == {"error": "Unknown user simple-user"}

    ret = client.post(
        reverse("lava.scheduler.internal.v1.workers"),
        data={"name": "worker-02", "username": "simple-user", "password": "mypass"},
    )
    assert ret.status_code == 200
    assert ret.json() == {
        "name": "worker-02",
        "token": Worker.objects.get(hostname="worker-02").token,
    }

    ret = client.post(
        reverse("lava.scheduler.internal.v1.workers"),
        data={"name": "worker-02", "username": "simple-user", "password": "mypass"},
    )
    assert ret.status_code == 403
    assert ret.json() == {"error": "Worker 'worker-02' already registered"}

    # Create a super user
    admin = User.objects.create_superuser("admin", "admin@example.com", "mypass")
    ret = client.post(
        reverse("lava.scheduler.internal.v1.workers"),
        data={"name": "worker-02", "username": "admin", "password": "mypass"},
    )
    assert ret.status_code == 200
    assert ret.json() == {
        "name": "worker-02",
        "token": Worker.objects.get(hostname="worker-02").token,
    }
