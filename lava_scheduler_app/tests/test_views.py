# -*- coding: utf-8 -*-
# Copyright (C) 2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA.  If not, see <http://www.gnu.org/licenses/>.

import pytest

from django.contrib.auth.models import Group, Permission, User
from django.urls import reverse

from lava_scheduler_app.models import (
    Alias,
    Device,
    DeviceType,
    GroupDevicePermission,
    TestJob,
    TestJobUser,
    Worker,
)


JOB_DEFINITION = """
device_type: juno
job_name: test
visibility: public
timeouts:
  job:
    minutes: 10
actions: []
"""


@pytest.fixture
def setup(db):
    group = Group.objects.create(name="group1")
    user = User.objects.create_user(username="tester", password="tester")  # nosec
    user.user_permissions.add(Permission.objects.get(codename="submit_testjob"))
    user.groups.add(group)
    dt_qemu = DeviceType.objects.create(name="qemu")
    Alias.objects.create(name="kvm", device_type=dt_qemu)
    Alias.objects.create(name="qemu-system", device_type=dt_qemu)
    dt_juno = DeviceType.objects.create(name="juno")
    worker_01 = Worker.objects.create(hostname="worker-01", state=Worker.STATE_OFFLINE)
    worker_02 = Worker.objects.create(hostname="worker-02", state=Worker.STATE_ONLINE)
    qemu_01 = Device.objects.create(
        hostname="qemu-01",
        device_type=dt_qemu,
        health=Device.HEALTH_MAINTENANCE,
        worker_host=worker_01,
    )
    juno_01 = Device.objects.create(
        hostname="juno-01",
        device_type=dt_juno,
        state=Device.STATE_RUNNING,
        health=Device.HEALTH_GOOD,
        worker_host=worker_02,
    )
    GroupDevicePermission.objects.assign_perm(Device.ADMIN_PERMISSION, group, juno_01)
    job_01 = TestJob.objects.create(
        description="test job 01",
        submitter=user,
        requested_device_type=dt_juno,
        actual_device=juno_01,
        state=TestJob.STATE_FINISHED,
        health=TestJob.HEALTH_COMPLETE,
        is_public=True,
    )
    job_02 = TestJob.objects.create(
        description="test job 02",
        submitter=user,
        requested_device_type=dt_juno,
        actual_device=juno_01,
        state=TestJob.STATE_RUNNING,
        is_public=True,
    )
    job_03 = TestJob.objects.create(
        description="test job 03", submitter=user, requested_device_type=dt_juno
    )


@pytest.mark.django_db
def test_index(client, setup):
    ret = client.get(reverse("lava.scheduler"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/index.html"  # nosec
    assert ret.context["device_status"] == "1/2"  # nosec
    assert ret.context["num_online"] == 1  # nosec
    assert ret.context["num_not_retired"] == 2  # nosec
    assert ret.context["num_jobs_running"] == 1  # nosec
    assert ret.context["num_devices_running"] == 1  # nosec


@pytest.mark.django_db
def test_devices(client, setup):
    ret = client.get(reverse("lava.scheduler.alldevices"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/alldevices.html"  # nosec
    assert len(ret.context["devices_table"].data) == 2  # nosec
    assert ret.context["devices_table"].data[0].hostname == "juno-01"  # nosec
    assert ret.context["devices_table"].data[1].hostname == "qemu-01"  # nosec


@pytest.mark.django_db
def test_devices_active(client, setup):
    ret = client.get(reverse("lava.scheduler.active_devices"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/activedevices.html"  # nosec
    assert len(ret.context["active_devices_table"].data) == 2  # nosec
    assert ret.context["active_devices_table"].data[0].hostname == "juno-01"  # nosec
    assert ret.context["active_devices_table"].data[1].hostname == "qemu-01"  # nosec


@pytest.mark.django_db
def test_devices_online(client, setup):
    ret = client.get(reverse("lava.scheduler.online_devices"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/onlinedevices.html"  # nosec
    assert len(ret.context["online_devices_table"].data) == 1  # nosec
    assert ret.context["online_devices_table"].data[0].hostname == "juno-01"  # nosec


@pytest.mark.django_db
def test_device_dcionary_plain(client, setup):
    ret = client.get(
        reverse("lava.scheduler.device.dictionary.plain", args=["qemu-01"])
    )
    assert ret.status_code == 200  # nosec
    assert ret.content != ""  # nosec


@pytest.mark.django_db
def test_devices_passing_health_check(client, setup):
    ret = client.get(reverse("lava.scheduler.passing_health_checks"))
    assert ret.status_code == 200  # nosec
    assert (  # nosec
        ret.templates[0].name == "lava_scheduler_app/passinghealthchecks.html"
    )
    assert len(ret.context["passing_health_checks_table"].data) == 2  # nosec
    assert (  # nosec
        ret.context["passing_health_checks_table"].data[0].hostname == "qemu-01"
    )
    assert (  # nosec
        ret.context["passing_health_checks_table"].data[1].hostname == "juno-01"
    )


@pytest.mark.django_db
def test_devices_my(client, setup):
    ret = client.get(reverse("lava.scheduler.mydevice_list"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/mydevices.html"  # nosec
    assert len(ret.context["my_device_table"].data) == 0  # nosec

    client.login(username="tester", password="tester")  # nosec
    ret = client.get(reverse("lava.scheduler.mydevice_list"))
    assert ret.status_code == 200  # nosec
    assert len(ret.context["my_device_table"].data) == 1  # nosec
    assert ret.context["my_device_table"].data[0].hostname == "juno-01"  # nosec


@pytest.mark.django_db
def test_devices_my_history_log(client, setup):
    ret = client.get(reverse("lava.scheduler.mydevices_health_history_log"))
    assert ret.status_code == 200  # nosec
    assert (  # nosec
        ret.templates[0].name == "lava_scheduler_app/mydevices_health_history_log.html"
    )
    assert len(ret.context["mydeviceshealthhistory_table"].data) == 0  # nosec

    client.login(username="tester", password="tester")  # nosec
    ret = client.get(reverse("lava.scheduler.mydevices_health_history_log"))
    assert ret.status_code == 200  # nosec
    assert len(ret.context["mydeviceshealthhistory_table"].data) == 0  # nosec


@pytest.mark.django_db
def test_devices_maintenance(client, setup):
    ret = client.get(reverse("lava.scheduler.maintenance_devices"))
    assert ret.status_code == 200  # nosec
    assert (  # nosec
        ret.templates[0].name == "lava_scheduler_app/maintenance_devices.html"
    )
    assert len(ret.context["maintenance_devices_table"].data) == 1  # nosec
    assert (  # nosec
        ret.context["maintenance_devices_table"].data[0].hostname == "qemu-01"
    )


@pytest.mark.django_db
def test_device_report(client, setup):
    ret = client.get(reverse("lava.scheduler.device_report", args=["juno-01"]))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/device_reports.html"  # nosec
    assert ret.context["device"].hostname == "juno-01"  # nosec
    assert len(ret.context["health_week_report"]) == 10  # nosec
    assert len(ret.context["job_week_report"]) == 10  # nosec
    assert len(ret.context["health_day_report"]) == 7  # nosec
    assert len(ret.context["job_day_report"]) == 7  # nosec


@pytest.mark.django_db
def test_device_types(client, setup):
    ret = client.get(reverse("lava.scheduler.device_types"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/alldevice_types.html"  # nosec
    assert len(ret.context["dt_table"].data) == 2  # nosec
    assert ret.context["dt_table"].data[0]["device_type"] == "juno"  # nosec
    assert ret.context["dt_table"].data[0]["idle"] == 0  # nosec
    assert ret.context["dt_table"].data[0]["busy"] == 1  # nosec
    assert ret.context["dt_table"].data[1]["device_type"] == "qemu"  # nosec
    assert ret.context["dt_table"].data[1]["idle"] == 0  # nosec


@pytest.mark.django_db
def test_device_type_health_history_log(client, setup):
    ret = client.get(
        reverse("lava.scheduler.device_type_health_history_log", args=["qemu"])
    )
    assert ret.status_code == 200  # nosec
    assert (  # nosec
        ret.templates[0].name
        == "lava_scheduler_app/device_type_health_history_log.html"
    )
    assert len(ret.context["dthealthhistory_table"].data) == 0  # nosec


@pytest.mark.django_db
def test_device_type_report(client, setup):
    ret = client.get(reverse("lava.scheduler.device_type_report", args=["juno"]))
    assert ret.status_code == 200  # nosec
    assert (  # nosec
        ret.templates[0].name == "lava_scheduler_app/devicetype_reports.html"
    )
    assert ret.context["device_type"].name == "juno"  # nosec
    assert len(ret.context["health_week_report"]) == 10  # nosec
    assert len(ret.context["job_week_report"]) == 10  # nosec
    assert len(ret.context["health_day_report"]) == 7  # nosec
    assert len(ret.context["job_day_report"]) == 7  # nosec


@pytest.mark.django_db
def test_device_types_detail(client, setup):
    ret = client.get(reverse("lava.scheduler.device_type.detail", args=["qemu"]))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/device_type.html"  # nosec
    assert ret.context["dt"].name == "qemu"  # nosec
    assert ret.context["cores"] == ""  # nosec
    assert ret.context["aliases"] == "kvm, qemu-system"  # nosec
    assert ret.context["all_devices_count"] == 1  # nosec
    assert ret.context["retired_devices_count"] == 0  # nosec
    assert ret.context["available_devices_count"] == 0  # nosec
    assert ret.context["available_devices_label"] == "danger"  # nosec
    assert ret.context["running_devices_count"] == 0  # nosec
    assert ret.context["queued_jobs_count"] == 0  # nosec
    assert ret.context["invalid_template"] is False  # nosec

    ret = client.get(reverse("lava.scheduler.device_type.detail", args=["juno"]))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/device_type.html"  # nosec
    assert ret.context["dt"].name == "juno"  # nosec
    assert ret.context["cores"] == ""  # nosec
    assert ret.context["aliases"] == ""  # nosec
    assert ret.context["all_devices_count"] == 1  # nosec
    assert ret.context["retired_devices_count"] == 0  # nosec
    assert ret.context["available_devices_count"] == 0  # nosec
    assert ret.context["available_devices_label"] == "warning"  # nosec
    assert ret.context["running_devices_count"] == 1  # nosec
    assert ret.context["queued_jobs_count"] == 1  # nosec
    assert ret.context["invalid_template"] is False  # nosec


@pytest.mark.django_db
def test_failure_report(client, setup):
    ret = client.get(reverse("lava.scheduler.failure_report"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/failure_report.html"  # nosec
    assert ret.context["device_type"] is None  # nosec
    assert ret.context["device"] is None  # nosec

    ret = client.get(reverse("lava.scheduler.failure_report") + "?device=juno-01")
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/failure_report.html"  # nosec
    assert ret.context["device_type"] is None  # nosec
    assert ret.context["device"] == "juno-01"  # nosec


@pytest.mark.django_db
def test_health_job_list(client, setup):
    ret = client.get(reverse("lava.scheduler.labhealth.detail", args=["juno-01"]))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/health_jobs.html"  # nosec
    assert ret.context["device"].hostname == "juno-01"  # nosec
    assert len(ret.context["health_job_table"].data) == 0  # nosec


@pytest.mark.django_db
def test_jobs(client, setup):
    ret = client.get(reverse("lava.scheduler.job.list"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/alljobs.html"  # nosec
    assert len(ret.context["alljobs_table"].data) == 2  # nosec
    assert ret.context["alljobs_table"].data[0].description == "test job 02"  # nosec
    assert ret.context["alljobs_table"].data[1].description == "test job 01"  # nosec


@pytest.mark.django_db
def test_jobs_active(client, setup):
    ret = client.get(reverse("lava.scheduler.job.active"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/active_jobs.html"  # nosec
    assert len(ret.context["active_jobs_table"].data) == 1  # nosec
    assert (  # nosec
        ret.context["active_jobs_table"].data[0].description == "test job 02"
    )


@pytest.mark.django_db
def test_jobs_my(client, setup):
    ret = client.get(reverse("lava.scheduler.myjobs"))
    assert ret.status_code == 404  # nosec

    assert client.login(username="tester", password="tester") is True  # nosec
    ret = client.get(reverse("lava.scheduler.myjobs"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/myjobs.html"  # nosec
    assert len(ret.context["myjobs_table"].data) == 3  # nosec
    assert ret.context["myjobs_table"].data[0].description == "test job 03"  # nosec
    assert ret.context["myjobs_table"].data[1].description == "test job 02"  # nosec
    assert ret.context["myjobs_table"].data[2].description == "test job 01"  # nosec


@pytest.mark.django_db
def test_job_errors(client, setup):
    ret = client.get(reverse("lava.scheduler.job.errors"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/job_errors.html"  # nosec
    assert len(ret.context["job_errors_table"].data) == 0  # nosec


@pytest.mark.django_db
def test_job_detail(client, setup):
    ret = client.get(
        reverse(
            "lava.scheduler.job.detail",
            args=[TestJob.objects.get(description="test job 01").pk],
        )
    )
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/job.html"  # nosec
    assert ret.context["log_data"] == []  # nosec


@pytest.mark.django_db
def test_job_definition(client, setup):
    ret = client.get(
        reverse(
            "lava.scheduler.job.definition",
            args=[TestJob.objects.get(description="test job 01").pk],
        )
    )
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/job_definition.html"  # nosec
    assert ret.context["job"].description == "test job 01"  # nosec


@pytest.mark.django_db
def test_job_definition_plain(client, setup):
    ret = client.get(
        reverse(
            "lava.scheduler.job.definition.plain",
            args=[TestJob.objects.get(description="test job 01").pk],
        )
    )
    assert ret.status_code == 200  # nosec
    assert ret.content == b""  # nosec


@pytest.mark.django_db
def test_job_description(client, monkeypatch, setup, tmpdir):
    (tmpdir / "job-01").mkdir()
    (tmpdir / "job-01" / "description.yaml").write_text(
        "Job description", encoding="utf-8"
    )
    monkeypatch.setattr(TestJob, "output_dir", str(tmpdir / "job-01"))

    job = TestJob.objects.get(description="test job 01")
    ret = client.get(reverse("lava.scheduler.job.description.yaml", args=[job.pk]))
    assert ret.status_code == 200  # nosec
    assert ret.content == b"Job description"  # nosec


@pytest.mark.django_db
def test_job_submit(client, setup):
    # Anonymous user GET
    ret = client.get(reverse("lava.scheduler.job.submit"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/job_submit.html"  # nosec
    assert ret.context["is_authorized"] is False  # nosec
    # Anonymous user POST
    ret = client.post(reverse("lava.scheduler.job.submit"), {"definition-input": ""})
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/job_submit.html"  # nosec
    assert ret.context["is_authorized"] is False  # nosec

    # Logged-user GET
    assert client.login(username="tester", password="tester") is True  # nosec
    ret = client.get(reverse("lava.scheduler.job.submit"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/job_submit.html"  # nosec
    assert ret.context["is_authorized"] is True  # nosec

    # Logged-user POST as JSON
    ret = client.post(
        reverse("lava.scheduler.job.submit"),
        {"definition-input": ""},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert ret.status_code == 200  # nosec
    assert ret.json() == {  # nosec
        "result": "success",
        "errors": "",
        "warnings": "expected a dictionary",
    }
    ret = client.post(
        reverse("lava.scheduler.job.submit"),
        {"definition-input": JOB_DEFINITION},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert ret.status_code == 200  # nosec
    assert ret.json() == {"result": "success", "errors": "", "warnings": ""}  # nosec

    # Logged-user POST
    ret = client.post(reverse("lava.scheduler.job.submit"), {"definition-input": "re"})
    assert ret.status_code == 200  # nosec
    assert ret.context["error"] == "expected a dictionary"  # nosec
    assert ret.context["context_help"] == "lava scheduler submit job"  # nosec
    assert ret.context["definition_input"] == "re"  # nosec

    # Success
    ret = client.post(
        reverse("lava.scheduler.job.submit"), {"definition-input": JOB_DEFINITION}
    )
    assert ret.status_code == 302  # nosec
    assert ret.url == "/scheduler/job/%d" % TestJob.objects.last().pk  # nosec

    # Success + is_favorite
    ret = client.post(
        reverse("lava.scheduler.job.submit"),
        {"definition-input": JOB_DEFINITION, "is_favorite": True},
    )
    assert ret.status_code == 302  # nosec
    assert ret.url == "/scheduler/job/%d" % TestJob.objects.last().pk  # nosec
    assert (  # nosec
        TestJobUser.objects.filter(user=User.objects.get(username="tester")).count()
        == 1
    )


@pytest.mark.django_db
def test_lab_health(client, setup):
    ret = client.get(reverse("lava.scheduler.labhealth"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/labhealth.html"  # nosec
    assert len(ret.context["device_health_table"].data) == 2  # nosec
    assert ret.context["device_health_table"].data[0].hostname == "juno-01"  # nosec
    assert ret.context["device_health_table"].data[1].hostname == "qemu-01"  # nosec


@pytest.mark.django_db
def test_report(client, setup):
    ret = client.get(reverse("lava.scheduler.reports"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/reports.html"  # nosec
    assert len(ret.context["health_week_report"]) == 10  # nosec
    assert len(ret.context["job_week_report"]) == 10  # nosec
    assert len(ret.context["health_day_report"]) == 7  # nosec
    assert len(ret.context["job_day_report"]) == 7  # nosec


@pytest.mark.django_db
def test_workers(client, setup):
    ret = client.get(reverse("lava.scheduler.workers"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/allworkers.html"  # nosec
    assert len(ret.context["worker_table"].data) == 3  # nosec
    assert ret.context["worker_table"].data[0].hostname == "example.com"  # nosec
    assert ret.context["worker_table"].data[1].hostname == "worker-01"  # nosec
    assert ret.context["worker_table"].data[2].hostname == "worker-02"  # nosec


@pytest.mark.django_db
def test_worker_detail(client, setup):
    ret = client.get(reverse("lava.scheduler.worker.detail", args=["worker-01"]))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/worker.html"  # nosec
    assert ret.context["worker"].hostname == "worker-01"  # nosec
    assert len(ret.context["worker_device_table"].data) == 1  # nosec
    assert ret.context["worker_device_table"].data[0].hostname == "qemu-01"  # nosec
    assert ret.context["can_admin"] is False  # nosec
