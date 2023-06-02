# Copyright (C) 2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from json import loads as json_loads
from pathlib import Path

import pytest
from django.contrib.auth.models import Group, User
from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from django.urls import reverse
from django.utils import timezone

from lava_common.yaml import yaml_safe_load
from lava_results_app.models import TestCase
from lava_scheduler_app.models import (
    Alias,
    Device,
    DeviceType,
    GroupDevicePermission,
    RemoteArtifactsAuth,
    TestJob,
    TestJobUser,
    Worker,
)
from lava_scheduler_app.views import (
    device_report_data,
    get_restricted_job,
    job_report_data,
    type_report_data,
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

TOKEN_JOB_DEFINITION = r"""
device_type: juno
actions:
- deploy:
    timeout:
      minutes: 35
    to: u-boot-ums
    os: oe
    image:
      url: http://test.org/test.img
      headers:
        PRIVATE: token
"""

NON_TOKEN_JOB_DEFINITION = r"""
device_type: juno
actions:
- deploy:
    timeout:
      minutes: 35
    to: u-boot-ums
    os: oe
    image:
      url: http://test.org/test.img
"""

INT_VALUE_JOB_DEFINITION = r"""
device_type: juno
actions:
- deploy:
    timeout:
      minutes: 35
    to: u-boot-ums
    os: oe
    image:
      url: http://test.org/test.img
    root_partition: 1
"""


@pytest.fixture
def setup(db):
    group = Group.objects.create(name="group1")
    admin = User.objects.create_user(
        username="admin", password="admin", is_superuser=True
    )  # nosec
    user = User.objects.create_user(username="tester", password="tester")  # nosec
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
    juno_02 = Device.objects.create(
        hostname="juno-02",
        device_type=dt_juno,
        state=Device.STATE_IDLE,
        health=Device.HEALTH_GOOD,
        worker_host=worker_02,
    )
    GroupDevicePermission.objects.assign_perm(Device.CHANGE_PERMISSION, group, juno_01)

    job_01 = TestJob.objects.create(
        description="test job 01",
        definition=TOKEN_JOB_DEFINITION,
        submitter=user,
        requested_device_type=dt_juno,
        actual_device=juno_01,
        state=TestJob.STATE_FINISHED,
        health=TestJob.HEALTH_COMPLETE,
        is_public=True,
        start_time=timezone.now(),
    )
    job_02 = TestJob.objects.create(
        description="test job 02",
        definition=NON_TOKEN_JOB_DEFINITION,
        submitter=user,
        requested_device_type=dt_juno,
        actual_device=juno_01,
        state=TestJob.STATE_RUNNING,
        is_public=True,
        start_time=timezone.now(),
    )
    job_03 = TestJob.objects.create(
        description="test job 03",
        submitter=user,
        state=TestJob.STATE_SUBMITTED,
        requested_device_type=dt_juno,
    )
    job_04 = TestJob.objects.create(
        description="test job 04",
        submitter=user,
        requested_device_type=dt_juno,
        actual_device=juno_01,
        state=TestJob.STATE_FINISHED,
        health=TestJob.HEALTH_INCOMPLETE,
        is_public=True,
        start_time=timezone.now(),
    )
    job_05 = TestJob.objects.create(
        description="test job 05",
        submitter=user,
        requested_device_type=dt_juno,
        actual_device=juno_02,
        state=TestJob.STATE_RUNNING,
        is_public=True,
        start_time=timezone.now(),
        target_group="group",
    )
    job_06 = TestJob.objects.create(
        description="test job 06",
        submitter=user,
        requested_device_type=dt_juno,
        actual_device=qemu_01,
        state=TestJob.STATE_RUNNING,
        is_public=True,
        health_check=True,
        start_time=timezone.now(),
        target_group="group",
    )


@pytest.mark.django_db
def test_index(client, setup):
    ret = client.get(reverse("lava.scheduler"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/index.html"  # nosec
    assert ret.context["num_online"] == 2  # nosec
    assert ret.context["num_not_retired"] == 3  # nosec
    assert ret.context["num_jobs_running"] == 3  # nosec
    assert ret.context["num_devices_running"] == 1  # nosec


@pytest.mark.django_db
def test_devices(client, setup):
    ret = client.get(reverse("lava.scheduler.alldevices"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/alldevices.html"  # nosec
    assert len(ret.context["devices_table"].data) == 3  # nosec
    assert ret.context["devices_table"].data[0].hostname == "juno-01"  # nosec
    assert ret.context["devices_table"].data[1].hostname == "juno-02"  # nosec
    assert ret.context["devices_table"].data[2].hostname == "qemu-01"  # nosec


@pytest.mark.django_db
def test_devices_active(client, setup):
    ret = client.get(reverse("lava.scheduler.active_devices"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/activedevices.html"  # nosec
    assert len(ret.context["active_devices_table"].data) == 3  # nosec
    assert ret.context["active_devices_table"].data[0].hostname == "juno-01"  # nosec
    assert ret.context["active_devices_table"].data[1].hostname == "juno-02"  # nosec
    assert ret.context["active_devices_table"].data[2].hostname == "qemu-01"  # nosec


@pytest.mark.django_db
def test_devices_online(client, setup):
    ret = client.get(reverse("lava.scheduler.online_devices"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/onlinedevices.html"  # nosec
    assert len(ret.context["online_devices_table"].data) == 2  # nosec
    assert ret.context["online_devices_table"].data[0].hostname == "juno-01"  # nosec
    assert ret.context["online_devices_table"].data[1].hostname == "juno-02"  # nosec


@pytest.mark.django_db
def test_device_dictionary(client, monkeypatch, setup):
    monkeypatch.setattr(
        Device, "load_configuration", lambda job_ctx, output_format: "data"
    )
    ret = client.get(reverse("lava.scheduler.device.dictionary", args=["qemu-01"]))
    assert ret.status_code == 200  # nosec
    assert ret.content != ""  # nosec


@pytest.mark.django_db
def test_device_dictionary_plain(client, setup):
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
    assert len(ret.context["passing_health_checks_table"].data) == 3  # nosec
    assert (  # nosec
        ret.context["passing_health_checks_table"].data[0].hostname == "qemu-01"
    )
    assert (  # nosec
        ret.context["passing_health_checks_table"].data[1].hostname == "juno-01"
    )
    assert (  # nosec
        ret.context["passing_health_checks_table"].data[2].hostname == "juno-02"
    )


@pytest.mark.django_db
def test_mydevice_list(client, setup):
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
def test_device_reports(client, setup):
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
    assert ret.context["dt_table"].data[0]["idle"] == 1  # nosec
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
def test_device_type_detail(client, setup):
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
    assert ret.context["all_devices_count"] == 2  # nosec
    assert ret.context["retired_devices_count"] == 0  # nosec
    assert ret.context["available_devices_count"] == 1  # nosec
    assert ret.context["available_devices_label"] == "warning"  # nosec
    assert ret.context["running_devices_count"] == 1  # nosec
    assert ret.context["queued_jobs_count"] == 1  # nosec
    assert ret.context["invalid_template"] is False  # nosec


@pytest.mark.django_db
def test_longest_jobs(client, monkeypatch, setup):
    assert client.login(username="tester", password="tester") is True  # nosec
    ret = client.post(reverse("lava.scheduler.longest_jobs"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/longestjobs.html"  # nosec
    assert len(ret.context["longestjobs_table"].data) == 3  # nosec
    assert (
        ret.context["longestjobs_table"].data[0].description == "test job 02"
    )  # nosec
    assert (
        ret.context["longestjobs_table"].data[1].description == "test job 05"
    )  # nosec
    assert (
        ret.context["longestjobs_table"].data[2].description == "test job 06"
    )  # nosec


@pytest.mark.django_db
def test_favorite_jobs_other_user(client, monkeypatch, setup):
    job_1 = TestJob.objects.get(description="test job 01")
    user = User.objects.get(username="tester")
    TestJobUser.objects.create(user=user, test_job=job_1, is_favorite=True)
    ret = client.post(reverse("lava.scheduler.favorite_jobs"), {"username": "tester"})
    assert ret.status_code == 200  # nosec
    assert ret.context["username"] == "tester"  # nosec
    assert len(ret.context["favoritejobs_table"].data) == 1  # nosec
    assert (
        ret.context["favoritejobs_table"].data[0].description == "test job 01"
    )  # nosec


@pytest.mark.django_db
def test_favorite_jobs(client, monkeypatch, setup):
    job_1 = TestJob.objects.get(description="test job 01")
    user = User.objects.get(username="tester")
    TestJobUser.objects.create(user=user, test_job=job_1, is_favorite=True)
    assert client.login(username="tester", password="tester") is True  # nosec
    ret = client.post(reverse("lava.scheduler.favorite_jobs"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/favorite_jobs.html"  # nosec
    assert len(ret.context["favoritejobs_table"].data) == 1  # nosec
    assert (
        ret.context["favoritejobs_table"].data[0].description == "test job 01"
    )  # nosec


@pytest.mark.django_db
def test_job_status(client, setup):
    job_1 = TestJob.objects.get(description="test job 01")
    ret = client.post(reverse("lava.scheduler.job_status", args=[job_1.pk]))
    assert ret.status_code == 200  # nosec
    response = json_loads(ret.content)
    assert response["X-JobState"] == "1"  # nosec
    assert response["started"] == "now"  # nosec
    assert (
        response["actual_device"]
        == '<a href="/scheduler/device/juno-01">juno-01</a> <a href="/scheduler/reports/device/juno-01"><span class="glyphicon glyphicon-stats"></span></a>'
    )  # nosec


@pytest.mark.django_db
def test_job_timing(client, monkeypatch, setup):
    monkeypatch.setattr(
        "lava_scheduler_app.logutils.logs_instance.read",
        lambda dir_name: """
- {"dt": "2019-11-05T09:06:14.952630", "lvl": "debug", "msg": "start: 1.1 deploy-device-env (timeout 00:03:52) [common]"}
- {"dt": "2019-11-05T09:06:14.953059", "lvl": "debug", "msg": "end: 1.1 deploy-device-env (duration 00:00:10) [common]"}
""",
    )
    job_1 = TestJob.objects.get(description="test job 01")
    ret = client.post(reverse("lava.scheduler.job.timing", args=[job_1.pk]))
    assert ret.status_code == 200  # nosec


@pytest.mark.django_db
def test_job_configuration(client, monkeypatch, setup):
    monkeypatch.setattr(TestJob, "output_dir", property(lambda x: "."))
    job_1 = TestJob.objects.get(description="test job 01")
    ret = client.post(reverse("lava.scheduler.job.configuration", args=[job_1.pk]))
    assert ret.status_code == 200  # nosec


@pytest.mark.django_db
def test_job_log_file_plain_no_log_file(client, monkeypatch, setup):
    job_1 = TestJob.objects.get(description="test job 01")
    ret = client.post(reverse("lava.scheduler.job.log_file.plain", args=[job_1.pk]))
    assert ret.status_code == 404  # nosec


@pytest.mark.django_db
def test_job_log_file_plain(client, monkeypatch, setup):
    monkeypatch.setattr(
        "lava_scheduler_app.logutils.logs_instance.open",
        lambda dir_name: """
line one
line two
""",
    )
    job_1 = TestJob.objects.get(description="test job 01")
    ret = client.post(reverse("lava.scheduler.job.log_file.plain", args=[job_1.pk]))
    assert ret.status_code == 200  # nosec
    assert (
        ret["Content-Disposition"] == "attachment; filename=job_%d.log" % job_1.id
    )  # nosec


@pytest.mark.django_db
def test_job_log_incremental_large_file(client, monkeypatch, setup):
    monkeypatch.setattr(
        "lava_scheduler_app.logutils.logs_instance.size", lambda dir_name: 100
    )
    monkeypatch.setattr(TestJob, "size_limit", property(lambda x: 99))

    job_1 = TestJob.objects.get(description="test job 01")
    ret = client.post(reverse("lava.scheduler.job.log_incremental", args=[job_1.pk]))
    assert ret.status_code == 200  # nosec
    assert ret["X-Size-Warning"] == "1"  # nosec


@pytest.mark.django_db
def test_job_log_incremental(client, monkeypatch, setup):
    monkeypatch.setattr(
        "lava_scheduler_app.logutils.logs_instance.size", lambda dir_name: 100
    )
    monkeypatch.setattr(
        "lava_scheduler_app.logutils.logs_instance.read",
        lambda dir_name, first_line: """
- {"dt": "2019-11-04T15:39:52.345099", "lvl": "results", "msg": {"case": "validate", "definition": "lava", "result": "pass"}}
- {"dt": "2019-11-04T15:39:52.345794", "lvl": "info", "msg": "start: 1 lxc-deploy (timeout 00:05:00) [tlxc]"}
""",
    )
    job_1 = TestJob.objects.get(description="test job 01")
    ret = client.post(reverse("lava.scheduler.job.log_incremental", args=[job_1.pk]))
    assert ret.status_code == 200  # nosec
    assert ret["X-Is-Finished"] == "1"  # nosec
    assert ret.json()[0]["msg"]["result"] == "pass"


@pytest.mark.django_db
def test_job_cancel_no_perm(client, setup):
    job_1 = TestJob.objects.get(description="test job 01")
    # The job is already finished: do not raise an exception
    ret = client.post(reverse("lava.scheduler.job.cancel", args=[job_1.pk]))
    assert ret.status_code == 302  # nosec
    # The job is running: raise an exception (permission denied)
    job_1.state = TestJob.STATE_RUNNING
    job_1.save()
    ret = client.post(reverse("lava.scheduler.job.cancel", args=[job_1.pk]))
    assert ret.status_code == 403  # nosec


@pytest.mark.django_db
def test_job_cancel_cannot_cancel(client, setup):
    assert client.login(username="tester", password="tester") is True  # nosec
    job_4 = TestJob.objects.get(description="test job 04")
    ret = client.post(reverse("lava.scheduler.job.cancel", args=[job_4.pk]))
    assert ret.status_code == 302  # nosec


@pytest.mark.django_db
def test_job_cancel(client, setup):
    assert client.login(username="tester", password="tester") is True  # nosec
    job_3 = TestJob.objects.get(description="test job 03")
    ret = client.post(reverse("lava.scheduler.job.cancel", args=[job_3.pk]))
    assert ret.status_code == 302  # nosec
    job_3.refresh_from_db()
    assert job_3.health == TestJob.HEALTH_CANCELED  # nosec
    assert job_3.state == TestJob.STATE_FINISHED  # nosec


@pytest.mark.django_db
def test_job_cancel_multinode(client, monkeypatch, setup):
    monkeypatch.setattr(TestJob, "essential_role", property(lambda x: False))
    assert client.login(username="tester", password="tester") is True  # nosec
    job_5 = TestJob.objects.get(description="test job 05")
    ret = client.post(reverse("lava.scheduler.job.cancel", args=[job_5.pk]))
    assert ret.status_code == 302  # nosec
    job_5.refresh_from_db()
    assert job_5.state == TestJob.STATE_CANCELING  # nosec
    job_6 = TestJob.objects.get(description="test job 06")
    assert job_6.state == TestJob.STATE_CANCELING  # nosec


@pytest.mark.django_db
def test_job_fail_no_perm(client, setup):
    assert client.login(username="tester", password="tester") is True  # nosec
    job_1 = TestJob.objects.get(description="test job 01")
    ret = client.post(reverse("lava.scheduler.job.fail", args=[job_1.pk]))
    assert ret.status_code == 403  # nosec


@pytest.mark.django_db
def test_job_fail_not_canceling(client, setup):
    assert client.login(username="admin", password="admin") is True  # nosec
    job_3 = TestJob.objects.get(description="test job 03")
    ret = client.post(reverse("lava.scheduler.job.fail", args=[job_3.pk]))
    assert ret.status_code == 403  # nosec


@pytest.mark.django_db
def test_job_fail(client, setup):
    assert client.login(username="admin", password="admin") is True  # nosec
    job_3 = TestJob.objects.get(description="test job 03")
    job_3.state = TestJob.STATE_CANCELING
    job_3.save()
    ret = client.post(reverse("lava.scheduler.job.fail", args=[job_3.pk]))
    assert ret.status_code == 302  # nosec
    job_3.refresh_from_db()
    assert job_3.health == TestJob.HEALTH_CANCELED  # nosec
    assert job_3.state == TestJob.STATE_FINISHED  # nosec


@pytest.mark.django_db
def test_job_resubmit_no_auth(client, setup):
    job_1 = TestJob.objects.get(description="test job 01")
    ret = client.post(reverse("lava.scheduler.job.resubmit", args=[job_1.pk]))
    assert ret.status_code == 403  # nosec


@pytest.mark.django_db
def test_job_resubmit_submission_failed(client, setup):
    job_1 = TestJob.objects.get(description="test job 01")
    assert client.login(username="tester", password="tester") is True  # nosec
    ret = client.post(
        reverse("lava.scheduler.job.resubmit", args=[job_1.pk]), {"is_resubmit": True}
    )
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/job_submit.html"
    assert ret.context["error"] == "a string or stream input is required"  # nosec


@pytest.mark.django_db
def test_job_resubmit_async_validate_error(client, monkeypatch, setup):
    monkeypatch.setattr(
        "lava_scheduler_app.views.validate_job", lambda job_definition: 1 / 0
    )
    job_1 = TestJob.objects.get(description="test job 01")
    assert client.login(username="tester", password="tester") is True  # nosec
    ret = client.post(
        reverse("lava.scheduler.job.resubmit", args=[job_1.pk]),
        {},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert ret.status_code == 200  # nosec
    assert ret.json() == {
        "errors": "division by zero",
        "result": "failure",
        "warnings": "",
    }  # nosec


@pytest.mark.django_db
def test_job_resubmit_async(client, monkeypatch, setup):
    monkeypatch.setattr(
        "lava_scheduler_app.views.validate_job", lambda job_definition: None
    )
    monkeypatch.setattr(
        "lava_scheduler_app.views.validate", lambda data, extra_context_variables: None
    )
    job_1 = TestJob.objects.get(description="test job 01")
    assert client.login(username="tester", password="tester") is True  # nosec
    ret = client.post(
        reverse("lava.scheduler.job.resubmit", args=[job_1.pk]),
        {"definition-input": ""},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert ret.status_code == 200  # nosec
    assert ret.json() == {"errors": "", "result": "success", "warnings": ""}  # nosec


@pytest.mark.django_db
def test_job_resubmit_load(client, setup):
    job_1 = TestJob.objects.get(description="test job 01")
    assert client.login(username="tester", password="tester") is True  # nosec
    ret = client.post(reverse("lava.scheduler.job.resubmit", args=[job_1.pk]))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/job_submit.html"


@pytest.mark.django_db
def test_job_resubmit(client, monkeypatch, setup):
    job_6 = TestJob.objects.get(description="test job 06")
    monkeypatch.setattr(
        "lava_scheduler_app.views.testjob_submission",
        lambda job_definition, user, original_job: job_6,
    )
    job_1 = TestJob.objects.get(description="test job 01")
    assert client.login(username="tester", password="tester") is True  # nosec
    ret = client.post(
        reverse("lava.scheduler.job.resubmit", args=[job_1.pk]), {"is_resubmit": True}
    )
    assert ret.status_code == 302  # nosec


@pytest.mark.django_db
def test_change_priority(client, setup):
    assert client.login(username="tester", password="tester") is True  # nosec
    job_1 = TestJob.objects.get(description="test job 01")
    ret = client.post(
        reverse("lava.scheduler.job.priority", args=[job_1.pk]), {"priority": 100}
    )
    assert ret.status_code == 302  # nosec
    job_1.refresh_from_db()
    assert job_1.priority == 100  # nosec


@pytest.mark.django_db
def test_job_toggle_favorite_no_auth(client, setup):
    ret = client.get(
        reverse(
            "lava.scheduler.job.toggle_favorite",
            args=[TestJob.objects.get(description="test job 01").pk],
        )
    )
    assert ret.status_code == 403  # nosec


@pytest.mark.django_db
def test_job_toggle_favorite(client, setup):
    assert client.login(username="tester", password="tester") is True  # nosec
    job_1 = TestJob.objects.get(description="test job 01")
    assert job_1.testjobuser_set.count() == 0  # nosec
    ret = client.get(reverse("lava.scheduler.job.toggle_favorite", args=[job_1.pk]))
    assert ret.status_code == 302  # nosec
    job_1.refresh_from_db()
    assert job_1.testjobuser_set.count() == 1  # nosec


@pytest.mark.django_db
def test_job_annotate_failure_no_auth(client, setup):
    ret = client.get(
        reverse(
            "lava.scheduler.job.annotate_failure",
            args=[TestJob.objects.get(description="test job 01").pk],
        )
    )
    assert ret.status_code == 403  # nosec


@pytest.mark.django_db
def test_job_annotate_failure_get(client, setup):
    assert client.login(username="admin", password="admin") is True  # nosec
    ret = client.get(
        reverse(
            "lava.scheduler.job.annotate_failure",
            args=[TestJob.objects.get(description="test job 01").pk],
        )
    )
    assert ret.status_code == 200  # nosec
    assert (
        ret.templates[0].name == "lava_scheduler_app/job_annotate_failure.html"
    )  # nosec


@pytest.mark.django_db
def test_job_annotate_failure_post(client, setup):
    assert client.login(username="tester", password="tester") is True  # nosec
    ret = client.post(
        reverse(
            "lava.scheduler.job.annotate_failure",
            args=[TestJob.objects.get(description="test job 01").pk],
        )
    )
    assert ret.status_code == 302  # nosec


@pytest.mark.django_db
def test_device_detail_non_existing(client, setup):
    ret = client.get(reverse("lava.scheduler.device.detail", args=["junox-03"]))
    assert ret.status_code == 404  # nosec


@pytest.mark.django_db
def test_device_detail(client, monkeypatch, setup):
    monkeypatch.setattr(Device, "load_configuration", lambda job_ctx: True)
    ret = client.get(reverse("lava.scheduler.device.detail", args=["juno-01"]))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/device.html"  # nosec

    assert ret.context["device"].hostname == "juno-01"  # nosec
    assert ret.context["can_change"] is False  # nosec
    assert ret.context["previous_device"] is None  # nosec
    assert ret.context["next_device"] == "juno-02"  # nosec
    assert ret.context["template_mismatch"] is False  # nosec


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
    ret = client.get(reverse("lava.scheduler.labhealth.detail", args=["qemu-01"]))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/health_jobs.html"  # nosec
    assert ret.context["device"].hostname == "qemu-01"  # nosec
    assert len(ret.context["health_job_table"].data) == 1  # nosec
    assert ret.context["health_job_table"].data[0].description == "test job 06"  # nosec


@pytest.mark.django_db
def test_jobs(client, setup):
    ret = client.get(reverse("lava.scheduler.job.list"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/alljobs.html"  # nosec
    assert len(ret.context["alljobs_table"].data) == 5  # nosec
    assert ret.context["alljobs_table"].data[0].description == "test job 06"  # nosec
    assert ret.context["alljobs_table"].data[1].description == "test job 05"  # nosec
    assert ret.context["alljobs_table"].data[2].description == "test job 04"  # nosec
    assert ret.context["alljobs_table"].data[3].description == "test job 02"  # nosec
    assert ret.context["alljobs_table"].data[4].description == "test job 01"  # nosec


@pytest.mark.django_db
def test_jobs_active(client, setup):
    ret = client.get(reverse("lava.scheduler.job.active"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/active_jobs.html"  # nosec
    assert len(ret.context["active_jobs_table"].data) == 3  # nosec
    assert (
        ret.context["active_jobs_table"].data[0].description == "test job 06"
    )  # nosec
    assert (
        ret.context["active_jobs_table"].data[1].description == "test job 05"
    )  # nosec
    assert (
        ret.context["active_jobs_table"].data[2].description == "test job 02"
    )  # nosec


@pytest.mark.django_db
def test_jobs_my(client, setup):
    ret = client.get(reverse("lava.scheduler.myjobs"))
    assert ret.status_code == 404  # nosec

    assert client.login(username="tester", password="tester") is True  # nosec
    ret = client.get(reverse("lava.scheduler.myjobs"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/myjobs.html"  # nosec
    assert len(ret.context["myjobs_table"].data) == 6  # nosec
    assert ret.context["myjobs_table"].data[0].description == "test job 06"  # nosec
    assert ret.context["myjobs_table"].data[1].description == "test job 05"  # nosec
    assert ret.context["myjobs_table"].data[2].description == "test job 04"  # nosec
    assert ret.context["myjobs_table"].data[3].description == "test job 03"  # nosec
    assert ret.context["myjobs_table"].data[4].description == "test job 02"  # nosec
    assert ret.context["myjobs_table"].data[5].description == "test job 01"  # nosec

    assert client.login(username="admin", password="admin") is True  # nosec
    ret = client.get(reverse("lava.scheduler.myjobs"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/myjobs.html"  # nosec
    assert len(ret.context["myjobs_table"].data) == 0  # nosec


@pytest.mark.django_db
def test_jobs_my_active(client, setup):
    ret = client.get(reverse("lava.scheduler.myjobs.active"))
    assert ret.status_code == 404  # nosec

    assert client.login(username="tester", password="tester") is True  # nosec
    ret = client.get(reverse("lava.scheduler.myjobs.active"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/myjobs_active.html"  # nosec
    assert len(ret.context["myjobs_active_table"].data) == 3  # nosec
    assert (
        ret.context["myjobs_active_table"].data[0].description == "test job 06"
    )  # nosec
    assert (
        ret.context["myjobs_active_table"].data[1].description == "test job 05"
    )  # nosec
    assert (
        ret.context["myjobs_active_table"].data[2].description == "test job 02"
    )  # nosec

    assert client.login(username="admin", password="admin") is True  # nosec
    ret = client.get(reverse("lava.scheduler.myjobs.active"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/myjobs_active.html"  # nosec
    assert len(ret.context["myjobs_active_table"].data) == 0  # nosec


@pytest.mark.django_db
def test_jobs_my_queued(client, setup):
    ret = client.get(reverse("lava.scheduler.myjobs.queued"))
    assert ret.status_code == 404  # nosec

    assert client.login(username="tester", password="tester") is True  # nosec
    ret = client.get(reverse("lava.scheduler.myjobs.queued"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/myjobs_queued.html"  # nosec
    assert len(ret.context["myjobs_queued_table"].data) == 1  # nosec
    assert (
        ret.context["myjobs_queued_table"].data[0].description == "test job 03"
    )  # nosec

    assert client.login(username="admin", password="admin") is True  # nosec
    ret = client.get(reverse("lava.scheduler.myjobs.queued"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/myjobs_queued.html"  # nosec
    assert len(ret.context["myjobs_queued_table"].data) == 0  # nosec


@pytest.mark.django_db
def test_jobs_my_error(client, setup):
    ret = client.get(reverse("lava.scheduler.myjobs.error"))
    assert ret.status_code == 404  # nosec

    assert client.login(username="tester", password="tester") is True  # nosec
    ret = client.get(reverse("lava.scheduler.myjobs.error"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/myjobs_error.html"  # nosec
    assert len(ret.context["myjobs_error_table"].data) == 0  # nosec

    assert client.login(username="admin", password="admin") is True  # nosec
    ret = client.get(reverse("lava.scheduler.myjobs.error"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/myjobs_error.html"  # nosec
    assert len(ret.context["myjobs_error_table"].data) == 0  # nosec


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
    assert ret.content == TOKEN_JOB_DEFINITION.encode()  # nosec


@pytest.mark.django_db
def test_job_description(client, monkeypatch, setup, tmp_path):
    (tmp_path / "job-01").mkdir()
    (tmp_path / "job-01" / "description.yaml").write_text(
        "Job description", encoding="utf-8"
    )
    monkeypatch.setattr(TestJob, "output_dir", str(tmp_path / "job-01"))

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
    assert ret.context["is_authorized"] == False  # nosec
    # Anonymous user POST
    ret = client.post(reverse("lava.scheduler.job.submit"), {"definition-input": ""})
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/job_submit.html"  # nosec
    assert ret.context["is_authorized"] == False  # nosec

    # Logged-user GET
    assert client.login(username="tester", password="tester") is True  # nosec
    ret = client.get(reverse("lava.scheduler.job.submit"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/job_submit.html"  # nosec
    assert ret.context["is_authorized"] == True  # nosec

    # Logged-user POST as JSON
    ret = client.post(
        reverse("lava.scheduler.job.submit"),
        {"definition-input": ""},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert ret.status_code == 200  # nosec
    assert ret.json() == {  # nosec
        "result": "failure",
        "errors": "expected a dictionary",
        "warnings": "",
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
    assert len(ret.context["device_health_table"].data) == 3  # nosec
    assert ret.context["device_health_table"].data[0]["hostname"] == "juno-01"  # nosec
    assert ret.context["device_health_table"].data[1]["hostname"] == "juno-02"  # nosec
    assert ret.context["device_health_table"].data[2]["hostname"] == "qemu-01"  # nosec


@pytest.mark.django_db
def test_reports(client, setup):
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
    assert ret.context["can_change"] is False  # nosec


@pytest.mark.django_db
def test_type_report_data_start_day_after_end_day(client, setup):
    dt = DeviceType.objects.get(name="qemu")
    result = type_report_data(5, 3, dt)
    # Assure there's no result for disambigous dates
    assert result[1]["fail"] == 0  # nosec
    assert result[1]["pass"] == 0  # nosec


@pytest.mark.django_db
def test_type_report_data(client, setup):
    dt = DeviceType.objects.get(name="juno")
    result = type_report_data(-1, 1, dt)
    assert result[1]["fail"] == 1  # nosec
    assert result[1]["pass"] == 1  # nosec


@pytest.mark.django_db
def test_device_report_data_start_day_after_end_day(client, setup):
    juno = Device.objects.get(hostname="juno-01")
    result = device_report_data(5, 3, juno)
    # Assure there's no result for disambigous dates
    assert result[1]["fail"] == 0  # nosec
    assert result[1]["pass"] == 0  # nosec


@pytest.mark.django_db
def test_device_report_data(client, setup):
    juno = Device.objects.get(hostname="juno-01")
    result = device_report_data(-1, 1, juno)
    assert result[1]["fail"] == 1  # nosec
    assert result[1]["pass"] == 1  # nosec


@pytest.mark.django_db
def test_job_report_start_day_after_end_day(client, setup):
    result = job_report_data(5, 3)
    # Assure there's no result for disambigous dates
    assert result[1]["fail"] == 0  # nosec
    assert result[1]["pass"] == 0  # nosec


@pytest.mark.django_db
def test_job_report(client, setup):
    result = job_report_data(-1, 1)
    assert result[1]["fail"] == 1  # nosec
    assert result[1]["pass"] == 1  # nosec


@pytest.mark.django_db
def test_device_health_no_perm(client, setup):
    device = Device.objects.get(hostname="qemu-01")
    assert client.login(username="tester", password="tester") is True  # nosec
    ret = client.post(
        reverse("lava.scheduler.device.health", kwargs={"pk": device.hostname}),
        {"health": "bad", "reason": "because"},
    )
    assert ret.status_code == 403  # nosec


@pytest.mark.django_db
def test_device_health_incorrect_health(client, setup):
    device = Device.objects.get(hostname="qemu-01")
    assert client.login(username="admin", password="admin") is True  # nosec
    ret = client.post(
        reverse("lava.scheduler.device.health", kwargs={"pk": device.hostname}),
        {"health": "non-existing-health", "reason": ""},
    )
    assert ret.status_code == 400  # nosec


@pytest.mark.django_db
def test_device_health(client, setup):
    device = Device.objects.get(hostname="qemu-01")
    assert device.health == 4  # nosec
    assert client.login(username="admin", password="admin") is True  # nosec
    ret = client.post(
        reverse("lava.scheduler.device.health", kwargs={"pk": device.hostname}),
        {"health": "bad", "reason": "because"},
    )
    assert ret.status_code == 302  # nosec
    device.refresh_from_db()
    assert device.health == 3  # nosec


@pytest.mark.django_db
def test_worker_health_no_perm(client, setup):
    worker = Worker.objects.get(hostname="worker-01")
    assert client.login(username="tester", password="tester") is True  # nosec
    ret = client.post(
        reverse("lava.scheduler.worker.health", kwargs={"pk": worker.hostname}),
        {"health": "Maintenance", "reason": "because"},
    )
    assert ret.status_code == 403  # nosec


@pytest.mark.django_db
def test_worker_health(client, setup):
    worker = Worker.objects.get(hostname="worker-01")
    assert worker.health == 0  # nosec
    assert client.login(username="admin", password="admin") is True  # nosec
    ret = client.post(
        reverse("lava.scheduler.worker.health", kwargs={"pk": worker.hostname}),
        {"health": "Maintenance", "reason": "because"},
    )
    assert ret.status_code == 302  # nosec
    worker.refresh_from_db()
    assert worker.health == 1  # nosec


@pytest.mark.django_db
def test_username_list_json_no_auth(client, setup):
    ret = client.get(reverse("lava.scheduler.username_list_json"), {"term": "t"})
    assert ret.status_code == 403  # nosec


@pytest.mark.django_db
def test_username_list_json(client, setup):
    assert client.login(username="tester", password="tester") is True  # nosec
    ret = client.get(reverse("lava.scheduler.username_list_json"), {"term": "t"})
    assert ret.status_code == 200  # nosec
    content = json_loads(ret.content)
    assert content[0]["name"] == "tester"  # nosec


@pytest.mark.django_db
def test_healthcheck(client, setup):
    ret = client.get(reverse("lava.scheduler.healthcheck"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/health_check_jobs.html"  # nosec
    assert len(ret.context["health_check_table"].data) == 1  # nosec
    assert (
        ret.context["health_check_table"].data[0].description == "test job 06"
    )  # nosec


@pytest.mark.django_db
def test_queue(client, setup):
    assert client.login(username="tester", password="tester") is True  # nosec
    ret = client.get(reverse("lava.scheduler.queue"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/queue.html"  # nosec
    assert len(ret.context["queue_table"].data) == 1  # nosec
    assert ret.context["queue_table"].data[0].description == "test job 03"  # nosec


@pytest.mark.django_db
def test_running(client, setup):
    ret = client.get(reverse("lava.scheduler.running"))
    assert ret.status_code == 200  # nosec
    assert ret.templates[0].name == "lava_scheduler_app/running.html"  # nosec
    assert len(ret.context["running_table"].data) == 2  # nosec
    assert ret.context["running_table"].data[0].name == "juno"  # nosec
    assert ret.context["running_table"].data[1].name == "qemu"  # nosec


@pytest.fixture
def check_request_auth_patched(monkeypatch):
    monkeypatch.setattr(
        "lava_scheduler_app.views.check_request_auth", lambda request, job: None
    )


@pytest.mark.django_db
def test_get_restricted_job_non_existing(client, check_request_auth_patched, setup):
    user = User.objects.get(username="tester")
    with pytest.raises(Http404):
        get_restricted_job(user, -1)


@pytest.mark.django_db
def test_get_restricted_job(client, check_request_auth_patched, setup):
    user = User.objects.get(username="tester")
    job = get_restricted_job(user, TestJob.objects.get(description="test job 01").pk)
    assert job.description == "test job 01"  # nosec


@pytest.mark.django_db
def test_download_device_type_template(client, monkeypatch, setup):
    monkeypatch.setattr(
        "lava_scheduler_app.views.load_devicetype_template",
        lambda dt, raw: "template data",
    )

    dt = DeviceType.objects.get(name="juno")
    assert client.login(username="tester", password="tester") is True  # nosec
    ret = client.post(
        reverse("lava_scheduler_download_device_type_yaml", kwargs={"pk": dt.name})
    )
    assert ret.status_code == 200  # nosec
    assert ret.content == b"template data"


@pytest.mark.django_db
def test_similar_jobs(client, setup):
    job_id = TestJob.objects.get(description="test job 01").pk
    # Anonymous user POST
    ret = client.post(reverse("lava.scheduler.job.similar_jobs", kwargs={"pk": job_id}))
    assert ret.status_code == 302  # nosec
    assert ret.url == "/results/query/+custom?entity=testjob&conditions="  # nosec
    # Logged-user POST
    assert client.login(username="tester", password="tester") is True  # nosec
    ret = client.post(
        reverse("lava.scheduler.job.similar_jobs", kwargs={"pk": job_id}),
        {
            "table": [ContentType.objects.get_for_model(TestJob).id],
            "field": ["actual_device"],
        },
    )
    assert ret.status_code == 302  # nosec
    assert (
        ret.url
        == "/results/query/+custom?entity=testjob&conditions=testjob__actual_device__exact__juno-01"
    )  # nosec


@pytest.mark.django_db
def test_internal_v1_jobs_test_auth_token(client, setup, mocker):
    user = User.objects.get(username="tester")
    job01 = TestJob.objects.get(description="test job 01")

    write_text = mocker.Mock()
    mocker.patch("pathlib.Path.write_text", write_text)

    ret = client.get(
        reverse("lava.scheduler.internal.v1.jobs", args=[job01.id]),
        HTTP_LAVA_TOKEN=job01.token,
    )
    assert ret.status_code == 200
    job_def = yaml_safe_load(ret.json()["definition"])

    # Token not in db.
    assert job_def["actions"][0]["deploy"]["image"]["headers"]["PRIVATE"] == "token"

    # Token in db.
    RemoteArtifactsAuth.objects.create(name="token", token="tokenvalue", user=user)
    ret = client.get(
        reverse("lava.scheduler.internal.v1.jobs", args=[job01.id]),
        HTTP_LAVA_TOKEN=job01.token,
    )
    assert ret.status_code == 200
    job_def = yaml_safe_load(ret.json()["definition"])

    assert (
        job_def["actions"][0]["deploy"]["image"]["headers"]["PRIVATE"] == "tokenvalue"
    )

    # No headers present.
    job02 = TestJob.objects.get(description="test job 02")
    ret = client.get(
        reverse("lava.scheduler.internal.v1.jobs", args=[job02.id]),
        HTTP_LAVA_TOKEN=job02.token,
    )
    assert ret.status_code == 200

    # Int value in deploy action dict
    job01.definition = INT_VALUE_JOB_DEFINITION
    job01.save()
    ret = client.get(
        reverse("lava.scheduler.internal.v1.jobs", args=[job01.id]),
        HTTP_LAVA_TOKEN=job01.token,
    )
    assert ret.status_code == 200
    job_def = yaml_safe_load(ret.json()["definition"])


@pytest.mark.django_db
def test_internal_v1_jobs_logs(client, setup, mocker):
    LOGS = """- {"dt": "2023-06-01T05:24:00.060423", "lvl": "info", "msg": "lava-dispatcher, installed at version: 2023.02"}
- {"dt": "2023-06-01T05:24:00.060872", "lvl": "info", "msg": "start: 0 validate"}
- {"dt": "2023-06-01T05:24:00.061082", "lvl": "info", "msg": "Start time: 2023-06-01 05:24:00.061063+00:00 (UTC)"}
- {"dt": "2023-06-01T05:24:00.061300", "lvl": "debug", "msg": "Validating that http://example.com/artefacts/debug/bl1.bin exists"}
- {"dt": "2023-06-01T05:24:00.435983", "lvl": "debug", "msg": "Validating that http://example.com/artefacts/debug/el3_payload.bin exists"}
- {"dt": "2023-06-01T05:24:00.448713", "lvl": "debug", "msg": "Validating that http://example.com/artefacts/debug/fip.bin exists"}
- {"dt": "2023-06-01T05:24:00.460928", "lvl": "debug", "msg": "Validating that http://example.com/artefacts/debug/ns_bl1u.bin exists"}
- {"dt": "2023-06-01T05:24:00.472695", "lvl": "info", "msg": "validate duration: 0.41"}
- {"dt": "2023-06-01T05:24:00.472852", "lvl": "results", "msg": {"case": "validate", "definition": "lava", "result": "pass"}}
- {"dt": "2023-06-01T05:24:00.473085", "lvl": "info", "msg": "start: 1 fvp-deploy (timeout 00:05:00) [common]"}
"""
    job = TestJob.objects.get(description="test job 02")

    # Missing token
    ret = client.post(
        reverse("lava.scheduler.internal.v1.jobs.logs", args=[job.id]),
    )
    assert ret.status_code == 400
    assert ret.json() == {"error": "Missing 'token'"}

    # Invalid token
    ret = client.post(
        reverse("lava.scheduler.internal.v1.jobs.logs", args=[job.id]),
        HTTP_LAVA_TOKEN="hello",
    )
    assert ret.status_code == 400
    assert ret.json() == {"error": "Invalid 'token'"}

    # Invalid data
    ret = client.post(
        reverse("lava.scheduler.internal.v1.jobs.logs", args=[job.id]),
        HTTP_LAVA_TOKEN=job.token,
    )
    assert ret.status_code == 400
    assert ret.json() == {"error": "Missing 'lines'"}

    ret = client.post(
        reverse("lava.scheduler.internal.v1.jobs.logs", args=[job.id]),
        {"lines": ["hello"]},
        HTTP_LAVA_TOKEN=job.token,
    )
    assert ret.status_code == 400
    assert ret.json() == {"error": "Missing 'index'"}

    ret = client.post(
        reverse("lava.scheduler.internal.v1.jobs.logs", args=[job.id]),
        {"lines": ["hello"], "index": "hello"},
        HTTP_LAVA_TOKEN=job.token,
    )
    assert ret.status_code == 400
    assert ret.json() == {"error": "Invalid 'index'"}

    # Valid data
    ret = client.post(
        reverse("lava.scheduler.internal.v1.jobs.logs", args=[job.id]),
        {"lines": LOGS, "index": 0},
        HTTP_LAVA_TOKEN=job.token,
    )
    assert ret.status_code == 200
    assert ret.json() == {"line_count": 10}

    assert (Path(job.output_dir) / "output.yaml").read_text(encoding="utf-8") == LOGS

    assert TestCase.objects.filter(suite__job=job).count() == 1
    tc = TestCase.objects.get(suite__job=job)
    assert tc.suite.name == "lava"
    assert tc.name == "validate"
    assert tc.result == TestCase.RESULT_PASS

    # Resend the same valid data
    ret = client.post(
        reverse("lava.scheduler.internal.v1.jobs.logs", args=[job.id]),
        {"lines": LOGS, "index": 0},
        HTTP_LAVA_TOKEN=job.token,
    )
    assert ret.status_code == 200
    assert ret.json() == {"line_count": 10}

    assert (Path(job.output_dir) / "output.yaml").read_text(encoding="utf-8") == LOGS

    assert TestCase.objects.filter(suite__job=job).count() == 1
    tc = TestCase.objects.get(suite__job=job)
    assert tc.suite.name == "lava"
    assert tc.name == "validate"
    assert tc.result == TestCase.RESULT_PASS
