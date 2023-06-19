# Copyright (C) 2018-2019 Linaro Limited
#
# Author: Milosz Wasilewski <milosz.wasilewski@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import csv
import json
import xml.etree.ElementTree as ET
from datetime import timedelta

import pytest
from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Group, User
from django.http import FileResponse, HttpResponse
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from lava_common.version import __version__
from lava_common.yaml import yaml_safe_load
from lava_rest_app import versions
from lava_results_app import models as result_models
from lava_scheduler_app.models import (
    Alias,
    Device,
    DeviceType,
    GroupDevicePermission,
    GroupDeviceTypePermission,
    Tag,
    TestJob,
    Worker,
)
from lava_server.files import File
from linaro_django_xmlrpc.models import AuthToken

EXAMPLE_JOB = """
job_name: test
visibility: public
timeouts:
  job:
    minutes: 10
  action:
    minutes: 5
actions: []
protocols: {}
"""

EXAMPLE_WORKING_JOB = """
device_type: public_device_type1
job_name: test
visibility: public
timeouts:
  job:
    minutes: 10
  action:
    minutes: 5
actions: []
protocols: {}
"""

EXAMPLE_WORKING_JOB_RESTRICTED_DEVICE_TYPE = """
device_type: restricted_device_type1
job_name: test
visibility: public
timeouts:
  job:
    minutes: 10
  action:
    minutes: 5
actions: []
protocols: {}
"""

LOG_FILE = """
- {"dt": "2018-10-03T16:28:28.199903", "lvl": "info", "msg": "lava-dispatcher, installed at version: 2018.7-1+stretch"}
- {"dt": "2018-10-03T16:28:28.200807", "lvl": "info", "msg": "start: 0 validate"}
"""

EXAMPLE_DEVICE = """
{% extends 'qemu.jinja2' %}
{% set mac_addr = 'BA:DD:AD:CC:09:01' %}
{% set memory = '1024' %}
{% set sync_to_lava = {'device_type': 'qemu', 'worker': 'worker0', 'tags': ['1gb', 'qemu01']} %}
"""


class TestRestApi:
    @pytest.fixture(autouse=True)
    def setUp(self, db):
        self.version = versions.versions[-1]  # use latest version by default

        # create users
        self.admin = User.objects.create(username="admin", is_superuser=True)
        self.admin_pwd = "supersecret"
        self.admin.set_password(self.admin_pwd)
        self.admin.save()
        self.user = User.objects.create(username="user1")
        self.user_pwd = "supersecret"
        self.user.set_password(self.user_pwd)
        self.user.save()
        self.user_no_token_pwd = "secret"
        self.user_no_token = User.objects.create(username="user2")
        self.user_no_token.set_password(self.user_no_token_pwd)
        self.user_no_token.save()

        self.group1 = Group.objects.create(name="group1")
        self.group2 = Group.objects.create(name="group2")
        self.user.groups.add(self.group2)
        admintoken = AuthToken.objects.create(  # nosec - unit test support
            user=self.admin, secret="adminkey"
        )
        self.usertoken = AuthToken.objects.create(  # nosec - unit test support
            user=self.user, secret="userkey"
        )
        # create second token to check whether authentication still works
        AuthToken.objects.create(user=self.user, secret="userkey2")  # nosec - unittest

        self.userclient = APIClient()
        self.userclient.credentials(HTTP_AUTHORIZATION="Token " + self.usertoken.secret)
        self.userclient_no_token = APIClient()
        self.adminclient = APIClient()
        self.adminclient.credentials(HTTP_AUTHORIZATION="Token " + admintoken.secret)

        # Create workers
        self.worker1 = Worker.objects.create(
            hostname="worker1", state=Worker.STATE_ONLINE, health=Worker.HEALTH_ACTIVE
        )
        self.worker2 = Worker.objects.create(
            hostname="worker2",
            state=Worker.STATE_OFFLINE,
            health=Worker.HEALTH_MAINTENANCE,
        )

        # create devicetypes
        self.public_device_type1 = DeviceType.objects.create(name="public_device_type1")
        self.restricted_device_type1 = DeviceType.objects.create(
            name="restricted_device_type1"
        )
        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.VIEW_PERMISSION, self.group1, self.restricted_device_type1
        )
        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.CHANGE_PERMISSION, self.group1, self.restricted_device_type1
        )
        self.invisible_device_type1 = DeviceType.objects.create(
            name="invisible_device_type1", display=False
        )

        Alias.objects.create(name="test1", device_type=self.public_device_type1)
        Alias.objects.create(name="test2", device_type=self.public_device_type1)
        Alias.objects.create(name="test3", device_type=self.invisible_device_type1)
        Alias.objects.create(name="test4", device_type=self.restricted_device_type1)

        # create devices
        self.public_device1 = Device.objects.create(
            hostname="public01",
            device_type=self.public_device_type1,
            worker_host=self.worker1,
        )
        self.public_device2 = Device.objects.create(
            hostname="public02",
            device_type=self.public_device_type1,
            worker_host=self.worker1,
            state=Device.STATE_RUNNING,
        )
        self.retired_device1 = Device.objects.create(
            hostname="retired01",
            device_type=self.public_device_type1,
            health=Device.HEALTH_RETIRED,
            worker_host=self.worker2,
        )
        self.restricted_device1 = Device.objects.create(
            hostname="restricted_device1",
            device_type=self.restricted_device_type1,
            worker_host=self.worker1,
        )
        GroupDevicePermission.objects.assign_perm(
            Device.VIEW_PERMISSION, self.group1, self.restricted_device1
        )
        GroupDevicePermission.objects.assign_perm(
            Device.CHANGE_PERMISSION, self.group1, self.restricted_device1
        )

        # create testjobs
        self.public_testjob1 = TestJob.objects.create(
            definition=EXAMPLE_WORKING_JOB,
            submitter=self.user,
            requested_device_type=self.public_device_type1,
            health=TestJob.HEALTH_INCOMPLETE,
            end_time=timezone.now(),
        )
        self.private_testjob1 = TestJob.objects.create(
            definition=EXAMPLE_JOB,
            submitter=self.admin,
            requested_device_type=self.restricted_device_type1,
            health=TestJob.HEALTH_COMPLETE,
            end_time=timezone.now(),
        )
        self.private_testjob1.submit_time = timezone.now() - timedelta(days=7)
        self.private_testjob1.save()

        # create logs

        # create results for testjobs
        self.public_lava_suite = result_models.TestSuite.objects.create(
            name="lava", job=self.public_testjob1
        )
        self.public_test_case1 = result_models.TestCase.objects.create(
            name="foo",
            suite=self.public_lava_suite,
            result=result_models.TestCase.RESULT_FAIL,
        )
        self.public_test_case2 = result_models.TestCase.objects.create(
            name="bar",
            suite=self.public_lava_suite,
            result=result_models.TestCase.RESULT_PASS,
        )
        self.private_lava_suite = result_models.TestSuite.objects.create(
            name="lava", job=self.private_testjob1
        )
        self.private_test_case1 = result_models.TestCase.objects.create(
            name="foo",
            suite=self.private_lava_suite,
            result=result_models.TestCase.RESULT_FAIL,
        )
        self.private_test_case2 = result_models.TestCase.objects.create(
            name="bar",
            suite=self.private_lava_suite,
            result=result_models.TestCase.RESULT_PASS,
        )
        self.tag1 = Tag.objects.create(name="tag1", description="description1")
        self.tag2 = Tag.objects.create(name="tag2", description="description2")

    def hit(self, client, url):
        response = client.get(url)
        assert response.status_code == 200  # nosec - unit test support

        if isinstance(response, HttpResponse):
            text = response.content.decode("utf-8")
            if response["Content-Type"] == "application/json":
                return json.loads(text)
            return text
        elif isinstance(response, FileResponse):
            return "".join(
                fragment.decode("utf-8") for fragment in response.streaming_content
            )
        else:
            raise TypeError("Unknown response type")

    def test_root(self):
        self.hit(self.userclient, reverse("api-root", args=[self.version]))

    def test_token(self):
        auth_dict = {
            "username": "%s" % self.user_no_token.get_username(),
            "password": self.user_no_token_pwd,
        }
        response = self.userclient_no_token.post(
            reverse("api-root", args=[self.version]) + "token/", auth_dict
        )
        assert response.status_code == 200  # nosec - unit test support
        text = response.content.decode("utf-8")
        assert "token" in json.loads(text).keys()  # nosec - unit test support

    def test_token_retrieval(self):
        auth_dict = {
            "username": "%s" % self.user.get_username(),
            "password": self.user_pwd,
        }
        response = self.userclient_no_token.post(
            reverse("api-root", args=[self.version]) + "token/", auth_dict
        )
        assert response.status_code == 200  # nosec - unit test support
        # response shouldn't cause exception. Below lines are just
        # additional check
        text = response.content.decode("utf-8")
        assert "token" in json.loads(text).keys()  # nosec - unit test support

    def test_testjobs(self):
        data = self.hit(
            self.userclient, reverse("api-root", args=[self.version]) + "jobs/"
        )
        assert len(data["results"]) == 1  # nosec - unit test support

    def test_testjobs_admin(self):
        data = self.hit(
            self.adminclient, reverse("api-root", args=[self.version]) + "jobs/"
        )
        assert len(data["results"]) == 2  # nosec - unit test support

    def test_testjob_item(self):
        self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/" % self.public_testjob1.id,
        )

    def test_testjob_logs(self, monkeypatch, tmp_path):
        (tmp_path / "output.yaml").write_text(LOG_FILE, encoding="utf-8")
        monkeypatch.setattr(TestJob, "output_dir", str(tmp_path))

        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/logs/" % self.public_testjob1.id,
        )
        # the value below depends on the log fragment used
        # be careful when changing either the value below or the log fragment
        assert len(data) == 203  # nosec - unit test support

    def test_testjob_logs_offset(self, monkeypatch, tmp_path):
        (tmp_path / "output.yaml").write_text(LOG_FILE, encoding="utf-8")
        monkeypatch.setattr(TestJob, "output_dir", str(tmp_path))

        # use start=2 as log lines count start from 1
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/logs/?start=2" % self.public_testjob1.id,
        )
        # the value below depends on the log fragment used
        # be careful when changing either the value below or the log fragment
        assert len(data) == 82  # nosec - unit test support

    def test_testjob_logs_offset_end(self, monkeypatch, tmp_path):
        (tmp_path / "output.yaml").write_text(LOG_FILE, encoding="utf-8")
        monkeypatch.setattr(TestJob, "output_dir", str(tmp_path))

        # use start=2 as log lines count start from 1
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/logs/?start=1&end=2" % self.public_testjob1.id,
        )
        # the value below depends on the log fragment used
        # be careful when changing either the value below or the log fragment
        assert len(data) == 120  # nosec - unit test support

    def test_testjob_logs_bad_offset(self, monkeypatch, tmp_path):
        (tmp_path / "output.yaml").write_text(LOG_FILE, encoding="utf-8")
        monkeypatch.setattr(TestJob, "output_dir", str(tmp_path))

        # use start=2 as log lines count start from 1
        response = self.userclient.get(
            reverse("api-root", args=[self.version])
            + "jobs/%s/logs/?start=2&end=1" % self.public_testjob1.id
        )
        assert response.status_code == 404  # nosec - unit test support

    def test_testjob_nologs(self):
        response = self.userclient.get(
            reverse("api-root", args=[self.version])
            + "jobs/%s/logs/" % self.public_testjob1.id
        )
        assert response.status_code == 404  # nosec - unit test support

    def test_testjob_suites(self):
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/suites/" % self.public_testjob1.id,
        )
        assert len(data["results"]) == 1  # nosec - unit test support

    def test_testjob_tests(self):
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/tests/" % self.public_testjob1.id,
        )
        assert len(data["results"]) == 2  # nosec - unit test support

    def test_testjob_tests_filter(self):
        data_pass = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/tests/?result=pass" % self.public_testjob1.id,
        )
        assert len(data_pass["results"]) == 1  # nosec - unit test support
        data_fail = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/tests/?result=fail" % self.public_testjob1.id,
        )
        assert len(data_fail["results"]) == 1  # nosec - unit test support
        data_skip = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/tests/?result=skip" % self.public_testjob1.id,
        )
        assert len(data_skip["results"]) == 0  # nosec - unit test support

    def test_testjob_suite(self):
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/suites/%s/"
            % (self.public_testjob1.id, self.public_testjob1.testsuite_set.first().id),
        )
        assert (
            data["id"] == self.public_testjob1.testsuite_set.first().id
        )  # nosec - unit test support

    def test_testjob_suite_tests(self):
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/suites/%s/tests/"
            % (self.public_testjob1.id, self.public_testjob1.testsuite_set.first().id),
        )
        assert len(data["results"]) == 2  # nosec - unit test support

    def test_testjob_suite_tests_filter(self):
        data_pass = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/suites/%s/tests/?result=pass"
            % (self.public_testjob1.id, self.public_testjob1.testsuite_set.first().id),
        )
        assert len(data_pass["results"]) == 1  # nosec - unit test support
        data_fail = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/suites/%s/tests/?result=fail"
            % (self.public_testjob1.id, self.public_testjob1.testsuite_set.first().id),
        )
        assert len(data_fail["results"]) == 1  # nosec - unit test support
        data_skip = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/suites/%s/tests/?result=skip"
            % (self.public_testjob1.id, self.public_testjob1.testsuite_set.first().id),
        )
        assert len(data_skip["results"]) == 0  # nosec - unit test support

    def test_testjob_suite_test(self):
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/suites/%s/tests/%s/"
            % (
                self.public_testjob1.id,
                self.public_testjob1.testsuite_set.first().id,
                self.public_testjob1.testsuite_set.first().testcase_set.first().id,
            ),
        )
        assert (
            data["id"]
            == self.public_testjob1.testsuite_set.first().testcase_set.first().id
        )  # nosec - unit test support

    def test_testjob_metadata(self):
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/metadata/" % self.public_testjob1.id,
        )
        assert data["metadata"] == []  # nosec - unit test support

    def test_testjob_csv(self):
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/csv/" % self.public_testjob1.id,
        )
        csv_data = csv.reader(data.splitlines())
        assert list(csv_data)[1][0] == str(
            self.public_testjob1.id
        )  # nosec - unit test support

    def test_testjob_yaml(self):
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/yaml/" % self.public_testjob1.id,
        )
        data = yaml_safe_load(data)
        assert data[0]["job"] == str(
            self.public_testjob1.id
        )  # nosec - unit test support

    def test_testjob_junit(self):
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/junit/" % self.public_testjob1.id,
        )
        tree = ET.fromstring(data)
        assert tree.tag == "testsuites"
        assert tree.attrib == {
            "failures": "1",
            "errors": "0",
            "tests": "2",
            "disabled": "0",
            "time": "0.0",
        }
        assert len(tree) == 1

        assert tree[0].tag == "testsuite"
        # Different junit_xml versions have additional fields; we have to
        # remove attrs here to support both bulseye and buster
        tree[0].attrib.pop("file", None)
        tree[0].attrib.pop("log", None)
        tree[0].attrib.pop("url", None)
        assert tree[0].attrib == {
            "name": "lava",
            "disabled": "0",
            "failures": "1",
            "errors": "0",
            "skipped": "0",
            "time": "0",
            "tests": "2",
            "timestamp": self.public_testjob1.end_time.isoformat(),
        }
        assert len(tree[0]) == 2

        assert tree[0][0].tag == "testcase"
        assert tree[0][0].attrib["name"] == "foo"
        assert tree[0][0].attrib["classname"] == "lava"
        assert "timestamp" in tree[0][0].attrib
        assert len(tree[0][0]) == 1

        assert tree[0][0][0].tag == "failure"
        assert tree[0][0][0].attrib == {"type": "failure", "message": "failed"}
        assert len(tree[0][0][0]) == 0

        assert tree[0][1].tag == "testcase"
        assert tree[0][1].attrib["name"] == "bar"
        assert tree[0][1].attrib["classname"] == "lava"
        assert "timestamp" in tree[0][0].attrib
        assert len(tree[0][1]) == 0

    def test_testjob_junit_classname_prefix(self):
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/junit/?classname_prefix=unique_id" % self.public_testjob1.id,
        )
        tree = ET.fromstring(data)
        assert tree[0][0].attrib["classname"] == "unique_id_lava"

    def test_testjob_tap13(self):
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/tap13/" % self.public_testjob1.id,
        )
        assert (  # nosec - unit test support
            data
            == """TAP version 13
1..2
# TAP results for lava
not ok 1 foo
ok 2 bar
"""
        )

    def test_testjob_suite_csv(self):
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/suites/%s/csv/"
            % (self.public_testjob1.id, self.public_testjob1.testsuite_set.first().id),
        )
        csv_data = csv.reader(data.splitlines())
        # Case id column is number 13 in a row.
        assert list(csv_data)[1][12] == str(
            self.public_testjob1.testsuite_set.first().testcase_set.first().id
        )  # nosec - unit test support

    def test_testjob_suite_yaml(self):
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/suites/%s/yaml/"
            % (self.public_testjob1.id, self.public_testjob1.testsuite_set.first().id),
        )
        data = yaml_safe_load(data)
        assert (
            data[0]["suite"] == self.public_testjob1.testsuite_set.first().name
        )  # nosec - unit test support

    def test_testjob_validate(self):
        response = self.userclient.post(
            reverse("api-root", args=[self.version]) + "jobs/validate/",
            {"definition": EXAMPLE_WORKING_JOB},
        )
        assert response.status_code == 200  # nosec - unit test support
        msg = json.loads(response.content)
        assert msg["message"] == "Job valid."

    def test_testjob_validate_testdef(self):
        "Test validating valid test definition."
        testdef = """
        metadata:
            format: Lava-Test Test Definition 1.0
            name: testdef validation
        parameters:
            key1: val1
        run:
            steps:
            - lava-test-case kernel-info --shell uname -a
        """
        response = self.userclient.post(
            reverse("api-root", args=[self.version]) + "jobs/validate_testdef/",
            {"definition": testdef},
        )
        assert response.status_code == 200  # nosec - unit test support
        msg = json.loads(response.content)
        assert msg["message"] == "Test definition valid."

    def test_testjob_validate_testdef_extra_key(self):
        "Test extra keys are allowed."
        testdef = """
        metadata:
            format: Lava-Test Test Definition 1.0
            name: testdef validation
            extra: allow extra
        """
        response = self.userclient.post(
            reverse("api-root", args=[self.version]) + "jobs/validate_testdef/",
            {"definition": testdef},
        )
        assert response.status_code == 200  # nosec - unit test support
        msg = json.loads(response.content)
        assert msg["message"] == "Test definition valid."

    def test_testjob_validate_testdef_missing_key(self):
        "Test test definition without required 'name' metadata is invalid."
        testdef = """
        metadata:
            format: Lava-Test Test Definition 1.0
        """
        response = self.userclient.post(
            reverse("api-root", args=[self.version]) + "jobs/validate_testdef/",
            {"definition": testdef},
        )
        assert response.status_code == 200  # nosec - unit test support
        msg = json.loads(response.content)
        assert (
            msg["message"]
            == "Test defnition invalid: required key not provided @ data['metadata']['name']"
        )

    def test_testjob_validate_testdef_wrong_key_type(self):
        "Test test definition key with wrong type is invalid."
        testdef = """
        metadata:
            format: Lava-Test Test Definition 1.0
            name: testdef validation
        parameters: wrong str type instead of dict
        """
        response = self.userclient.post(
            reverse("api-root", args=[self.version]) + "jobs/validate_testdef/",
            {"definition": testdef},
        )
        assert response.status_code == 200  # nosec - unit test support
        msg = json.loads(response.content)
        assert (
            msg["message"]
            == "Test defnition invalid: expected dict for dictionary value @ data['parameters']"
        )

    def test_testjobs_filters(self):
        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version]) + "jobs/?health=Incomplete",
        )
        assert len(data["results"]) == 1  # nosec - unit test support

        job1_submit_time = timezone.make_naive(self.public_testjob1.submit_time)
        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version])
            + "jobs/?submit_time=%s" % job1_submit_time,
        )
        assert len(data["results"]) == 1  # nosec - unit test support

        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version])
            + "jobs/?submit_time__lt=%s" % job1_submit_time,
        )
        assert len(data["results"]) == 1  # nosec - unit test support

        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version])
            + "jobs/?definition__contains=public_device",
        )
        assert len(data["results"]) == 1  # nosec - unit test support

    def test_devices_list(self):
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version]) + "devices/?ordering=hostname",
        )
        assert len(data["results"]) == 2  # nosec - unit test support
        assert data["results"][0]["hostname"] == "public01"  # nosec - unit test support
        assert data["results"][1]["hostname"] == "public02"  # nosec - unit test support

    def test_devices_admin(self):
        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version]) + "devices/?ordering=hostname",
        )
        assert len(data["results"]) == 3  # nosec - unit test support
        assert data["results"][0]["hostname"] == "public01"  # nosec - unit test support
        assert data["results"][1]["hostname"] == "public02"  # nosec - unit test support
        assert (
            data["results"][2]["hostname"] == "restricted_device1"
        )  # nosec - unit test support

    def test_devices_retrieve(self):
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version]) + "devices/public01/",
        )
        assert data["hostname"] == "public01"  # nosec - unit test support
        assert data["device_type"] == "public_device_type1"  # nosec - unit test support

    def test_devices_create_unauthorized(self):
        response = self.userclient.post(
            reverse("api-root", args=[self.version]) + "devices/",
            {
                "hostname": "public03",
                "device_type": "qemu",
                "health": "Idle",
                "pysical_owner": "admin",
            },
        )
        assert response.status_code == 403  # nosec - unit test support

    def test_devices_create(self):
        response = self.adminclient.post(
            reverse("api-root", args=[self.version]) + "devices/",
            {
                "hostname": "public03",
                "device_type": "public_device_type1",
                "health": "Good",
                "pysical_owner": "admin",
            },
        )
        assert response.status_code == 201  # nosec - unit test support

    def test_devices_delete_unauthorized(self):
        response = self.userclient.delete(
            reverse("api-root", args=[self.version]) + "devices/public02/"
        )
        assert response.status_code == 403  # nosec - unit test support

    def test_devices_delete(self):
        response = self.adminclient.delete(
            reverse("api-root", args=[self.version]) + "devices/public02/"
        )
        assert response.status_code == 204  # nosec - unit test support

    def test_devices_update_unauthorized(self):
        response = self.userclient.put(
            reverse("api-root", args=[self.version]) + "devices/public02/",
            {"device_type": "restricted_device_type1"},
        )
        assert response.status_code == 403  # nosec - unit test support

    def test_devices_update(self):
        # Set health
        response = self.adminclient.put(
            reverse("api-root", args=[self.version]) + "devices/public02/",
            {"device_type": "restricted_device_type1", "health": "Unknown"},
        )
        assert response.status_code == 200  # nosec - unit test support
        content = json.loads(response.content.decode("utf-8"))
        assert (
            content["device_type"] == "restricted_device_type1"
        )  # nosec - unit test support
        assert content["health"] == "Unknown"  # nosec - unit test support
        assert Device.objects.get(hostname="public02").get_health_display() == "Unknown"
        assert LogEntry.objects.filter(object_id="public02").count() == 1
        assert LogEntry.objects.get(object_id="public02").user == self.admin
        assert (
            LogEntry.objects.get(object_id="public02").change_message
            == "Maintenance → Unknown"
        )

        # Set health again
        response = self.adminclient.patch(
            reverse("api-root", args=[self.version]) + "devices/public02/",
            {"health": "Good"},
        )
        assert response.status_code == 200  # nosec - unit test support
        content = json.loads(response.content.decode("utf-8"))
        assert content["health"] == "Good"  # nosec - unit test support
        assert Device.objects.get(hostname="public02").get_health_display() == "Good"
        assert LogEntry.objects.filter(object_id="public02").count() == 2
        logentry = (
            LogEntry.objects.filter(object_id="public02").order_by("action_time").last()
        )
        assert logentry.user == self.admin
        assert logentry.change_message == "Unknown → Good"

    def test_devices_get_dictionary(self, monkeypatch, tmp_path):
        # invalid context
        response = self.userclient.get(
            reverse("api-root", args=[self.version])
            + "devices/public01/dictionary/?context={{"
        )
        assert response.status_code == 400  # nosec

        # no device dict
        monkeypatch.setattr(
            Device, "load_configuration", (lambda self, job_ctx, output_format: None)
        )
        response = self.userclient.get(
            reverse("api-root", args=[self.version]) + "devices/public01/dictionary/"
        )
        assert response.status_code == 400  # nosec

        # success
        monkeypatch.setattr(
            Device,
            "load_configuration",
            (lambda self, job_ctx, output_format: "device: dict"),
        )
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version]) + "devices/public01/dictionary/",
        )
        data = yaml_safe_load(data)
        assert data == {"device": "dict"}  # nosec

    def test_devices_set_health(self):
        response = self.adminclient.post(
            reverse("api-root", args=[self.version]) + "devices/public01/set_health/",
            {"health": "Maintenance", "reason": "Foo"},
        )
        assert response.status_code == 202
        device_details_request = self.adminclient.get(
            reverse("api-root", args=[self.version]) + "devices/public01/"
        )
        assert device_details_request.status_code == 200
        device_details = device_details_request.json()
        assert device_details["health"] == "Maintenance"
        logentry = LogEntry.objects.filter(object_id=device_details["hostname"]).first()
        assert "Foo" in logentry.change_message

    def test_devices_set_dictionary(self, monkeypatch, tmp_path):
        def save_configuration(self, data):
            assert data == "hello"  # nosec
            return True

        monkeypatch.setattr(Device, "save_configuration", save_configuration)

        response = self.adminclient.post(
            reverse("api-root", args=[self.version]) + "devices/public01/dictionary/",
            {"dictionary": "hello"},
        )
        assert response.status_code == 200  # nosec

        # No dictionary param.
        response = self.adminclient.post(
            reverse("api-root", args=[self.version]) + "devices/public01/dictionary/"
        )
        assert response.status_code == 400  # nosec

    def test_devices_validate(self):
        response = self.userclient.post(
            reverse("api-root", args=[self.version]) + "devices/validate/",
            data=EXAMPLE_DEVICE,
            content_type="text/plain",
        )
        assert response.status_code == 200  # nosec - unit test support
        msg = json.loads(response.content)
        assert msg["message"] == "Device dictionary valid."

    def test_devices_filters(self):
        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version]) + "devices/?state=Idle",
        )
        assert len(data["results"]) == 2  # nosec - unit test support

        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version]) + "devices/?health=Retired",
        )
        assert len(data["results"]) == 0  # nosec - unit test support

        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version])
            + "devices/?all=True&health=Retired",
        )
        assert len(data["results"]) == 1  # nosec - unit test support

        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version])
            + "devices/?hostname__contains=public",
        )
        assert len(data["results"]) == 2  # nosec - unit test support

    def test_devicetypes(self):
        data = self.hit(
            self.userclient, reverse("api-root", args=[self.version]) + "devicetypes/"
        )
        assert len(data["results"]) == 2  # nosec - unit test support

    def test_devicetypes_admin(self):
        data = self.hit(
            self.adminclient, reverse("api-root", args=[self.version]) + "devicetypes/"
        )
        assert len(data["results"]) == 3  # nosec - unit test support

    def test_devicetype_view(self):
        response = self.userclient.get(
            reverse("api-root", args=[self.version])
            + "devicetypes/%s/" % self.public_device_type1.name
        )
        assert response.status_code == 200  # nosec - unit test support

    def test_devicetype_view_unauthorized(self):
        response = self.userclient.get(
            reverse("api-root", args=[self.version])
            + "devicetypes/%s/" % self.restricted_device_type1.name
        )
        assert response.status_code == 404  # nosec - unit test support

    def test_devicetype_view_admin(self):
        response = self.adminclient.get(
            reverse("api-root", args=[self.version])
            + "devicetypes/%s/" % self.restricted_device_type1.name
        )
        assert response.status_code == 200  # nosec - unit test support

    def test_devicetype_create_unauthorized(self):
        response = self.userclient.post(
            reverse("api-root", args=[self.version]) + "devicetypes/", {"name": "bbb"}
        )
        assert response.status_code == 403  # nosec - unit test support

    def test_devicetype_create_no_name(self):
        response = self.adminclient.post(
            reverse("api-root", args=[self.version]) + "devicetypes/", {}
        )
        assert response.status_code == 400  # nosec - unit test support

    def test_devicetype_create(self):
        response = self.adminclient.post(
            reverse("api-root", args=[self.version]) + "devicetypes/", {"name": "bbb"}
        )
        assert response.status_code == 201  # nosec - unit test support

    def test_devicetype_get_template(self, mocker, tmp_path):
        (tmp_path / "qemu.jinja2").write_text("hello", encoding="utf-8")
        mocker.patch(
            "lava_server.files.File.KINDS",
            {"device-type": ([str(tmp_path)], "{name}.jinja2")},
        )

        # 1. normal case
        qemu_device_type1 = DeviceType.objects.create(name="qemu")
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "devicetypes/%s/template/" % qemu_device_type1.name,
        )
        data = yaml_safe_load(data)
        assert data == "hello"  # nosec

        # 2. Can't read the file
        bbb_device_type1 = DeviceType.objects.create(name="bbb")
        response = self.userclient.get(
            reverse("api-root", args=[self.version])
            + "devicetypes/%s/template/" % bbb_device_type1.name
        )
        assert response.status_code == 400  # nosec

    def test_devicetype_set_template(self, mocker, tmp_path):
        mocker.patch(
            "lava_server.files.File.KINDS",
            {"device-type": ([str(tmp_path)], "{name}.jinja2")},
        )

        # 1. normal case
        qemu_device_type1 = DeviceType.objects.create(name="qemu")
        response = self.adminclient.post(
            reverse("api-root", args=[self.version])
            + "devicetypes/%s/template/" % qemu_device_type1.name,
            {"template": "hello world"},
        )
        assert response.status_code == 204  # nosec - unit test support
        assert (tmp_path / "qemu.jinja2").read_text(
            encoding="utf-8"
        ) == "hello world"  # nosec

    def test_devicetype_get_health_check(self, mocker, tmp_path):
        (tmp_path / "qemu.yaml").write_text("hello", encoding="utf-8")
        mocker.patch(
            "lava_server.files.File.KINDS",
            {"health-check": ([str(tmp_path)], "{name}.yaml")},
        )

        # 1. normal case
        qemu_device_type1 = DeviceType.objects.create(name="qemu")
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "devicetypes/%s/health_check/" % qemu_device_type1.name,
        )
        data = yaml_safe_load(data)
        assert data == "hello"  # nosec

        # 2. Can't read the health-check
        docker_device_type1 = DeviceType.objects.create(name="docker")
        response = self.userclient.get(
            reverse("api-root", args=[self.version])
            + "devicetypes/%s/health_check/" % docker_device_type1.name
        )
        assert response.status_code == 400  # nosec

    def test_devicetype_set_health_check(self, mocker, tmp_path):
        mocker.patch(
            "lava_server.files.File.KINDS",
            {"health-check": ([str(tmp_path)], "{name}.yaml")},
        )

        # 1. normal case
        qemu_device_type1 = DeviceType.objects.create(name="qemu")
        response = self.adminclient.post(
            reverse("api-root", args=[self.version])
            + "devicetypes/%s/health_check/" % qemu_device_type1.name,
            {"config": "hello world"},
        )
        assert response.status_code == 204  # nosec - unit test support
        assert (tmp_path / "qemu.yaml").read_text(
            encoding="utf-8"
        ) == "hello world"  # nosec

    def test_devicetype_filters(self):
        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version]) + "devicetypes/?display=True",
        )
        assert len(data["results"]) == 2  # nosec - unit test support

        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version])
            + "devicetypes/?display__in=True,False",
        )
        assert len(data["results"]) == 3  # nosec - unit test support

        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version])
            + "devicetypes/?name__contains=public",
        )
        assert len(data["results"]) == 1  # nosec - unit test support

        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version])
            + "devicetypes/?name__in=public_device_type1,restricted_device_type1",
        )
        assert len(data["results"]) == 2  # nosec - unit test support

    def test_workers_list(self):
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version]) + "workers/?ordering=hostname",
        )
        # We get 3 workers because the default one (example.com) is always
        # created by the migrations
        assert len(data["results"]) == 3  # nosec - unit test support
        assert (  # nosec - unit test support
            data["results"][0]["hostname"] == "example.com"
        )
        assert data["results"][1]["hostname"] == "worker1"  # nosec - unit test support
        assert data["results"][1]["health"] == "Active"  # nosec - unit test support
        assert data["results"][1]["state"] == "Online"  # nosec - unit test support
        assert data["results"][2]["hostname"] == "worker2"  # nosec - unit test support
        assert (  # nosec - unit test support
            data["results"][2]["health"] == "Maintenance"
        )
        assert data["results"][2]["state"] == "Offline"  # nosec - unit test support

    def test_workers_retrieve(self):
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "workers/%s/" % self.worker1.hostname,
        )
        assert data["hostname"] == "worker1"  # nosec - unit test support
        assert data["state"] == "Online"  # nosec - unit test support
        assert data["health"] == "Active"  # nosec - unit test support

    def test_workers_retrieve_with_dot(self):
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version]) + "workers/example.com/",
        )
        assert data["hostname"] == "example.com"  # nosec - unit test support
        assert data["state"] == "Offline"  # nosec - unit test support
        assert data["health"] == "Active"  # nosec - unit test support

    def test_workers_create_unauthorized(self):
        response = self.userclient.post(
            reverse("api-root", args=[self.version]) + "workers/",
            {"hostname": "worker3", "description": "description3"},
        )
        assert response.status_code == 403  # nosec - unit test support

    def test_workers_create(self):
        response = self.adminclient.post(
            reverse("api-root", args=[self.version]) + "workers/",
            {"hostname": "worker3", "description": "description3"},
        )
        assert response.status_code == 201  # nosec - unit test support

    def test_workers_delete_unauthorized(self):
        response = self.userclient.delete(
            reverse("api-root", args=[self.version])
            + "workers/%s/" % self.worker2.hostname
        )
        assert response.status_code == 403  # nosec - unit test support

    def test_workers_delete(self):
        response = self.adminclient.delete(
            reverse("api-root", args=[self.version])
            + "workers/%s/" % self.worker2.hostname
        )
        assert response.status_code == 204  # nosec - unit test support

    def test_workers_get_env(self, mocker, tmp_path):
        (tmp_path / "env.yaml").write_text("hello", encoding="utf-8")
        mocker.patch(
            "lava_server.files.File.KINDS",
            {"env": [str(tmp_path / "{name}/env.yaml"), str(tmp_path / "env.yaml")]},
        )

        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "workers/%s/env/" % self.worker1.hostname,
        )
        data = yaml_safe_load(data)
        assert data == "hello"  # nosec

        # worker does not exists
        response = self.userclient.get(
            reverse("api-root", args=[self.version]) + "workers/invalid_hostname/env/"
        )
        assert response.status_code == 404  # nosec

        # no configuration file
        (tmp_path / "env.yaml").unlink()
        response = self.userclient.get(
            reverse("api-root", args=[self.version])
            + "workers/%s/env/" % self.worker1.hostname
        )
        assert response.status_code == 400  # nosec

    def test_workers_get_config(self, mocker, tmp_path):
        (tmp_path / self.worker1.hostname).mkdir()
        (tmp_path / self.worker1.hostname / "dispatcher.yaml").write_text(
            "hello world", encoding="utf-8"
        )
        mocker.patch(
            "lava_server.files.File.KINDS",
            {
                "dispatcher": [
                    str(tmp_path / "{name}/dispatcher.yaml"),
                    str(tmp_path / "{name}.yaml"),
                ]
            },
        )
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "workers/%s/config/" % self.worker1.hostname,
        )
        data = yaml_safe_load(data)
        assert data == "hello world"  # nosec

        # worker does not exists
        response = self.userclient.get(
            reverse("api-root", args=[self.version])
            + "workers/invalid_hostname/config/"
        )
        assert response.status_code == 404  # nosec

        # no configuration file
        (tmp_path / self.worker1.hostname / "dispatcher.yaml").unlink()
        (tmp_path / self.worker1.hostname).rmdir()
        response = self.userclient.get(
            reverse("api-root", args=[self.version])
            + "workers/%s/config/" % self.worker1.hostname
        )
        assert response.status_code == 400  # nosec

    def test_workers_set_env(self, mocker, tmp_path):
        mocker.patch(
            "lava_server.files.File.KINDS",
            {
                "env": [
                    str(tmp_path / "dispatcher.d/{name}/env.yaml"),
                    str(tmp_path / "env.yaml"),
                ]
            },
        )
        response = self.adminclient.post(
            reverse("api-root", args=[self.version])
            + "workers/%s/env/" % self.worker1.hostname,
            {"env": "hello"},
        )
        assert response.status_code == 200  # nosec
        assert File("env", self.worker1.hostname).read() == "hello"

        # worker does not exists
        response = self.adminclient.post(
            reverse("api-root", args=[self.version]) + "workers/invalid_hostname/env/",
            {"env": "hello"},
        )
        assert response.status_code == 404  # nosec

        # insufficient permissions
        response = self.userclient.post(
            reverse("api-root", args=[self.version])
            + "workers/%s/env/" % self.worker1.hostname,
            {"env": "hello"},
        )
        assert response.status_code == 403  # nosec

        # No env parameter
        response = self.adminclient.post(
            reverse("api-root", args=[self.version])
            + "workers/%s/env/" % self.worker1.hostname
        )
        assert response.status_code == 400  # nosec

    def test_workers_set_config(self, mocker, tmp_path):
        mocker.patch(
            "lava_server.files.File.KINDS",
            {
                "dispatcher": [
                    str(tmp_path / "{name}/dispatcher.yaml"),
                    str(tmp_path / "{name}.yaml"),
                ]
            },
        )
        response = self.adminclient.post(
            reverse("api-root", args=[self.version])
            + "workers/%s/config/" % self.worker1.hostname,
            {"config": "hello"},
        )
        assert response.status_code == 200  # nosec
        assert File("dispatcher", self.worker1.hostname).read() == "hello"

        # worker does not exists
        response = self.adminclient.post(
            reverse("api-root", args=[self.version])
            + "workers/invalid_hostname/config/",
            {"config": "hello"},
        )
        assert response.status_code == 404  # nosec

        # insufficient permissions
        response = self.userclient.post(
            reverse("api-root", args=[self.version])
            + "workers/%s/config/" % self.worker1.hostname,
            {"config": "hello"},
        )
        assert response.status_code == 403  # nosec

        # No config parameter
        response = self.adminclient.post(
            reverse("api-root", args=[self.version])
            + "workers/%s/config/" % self.worker1.hostname
        )
        assert response.status_code == 400  # nosec

    def test_workers_filters(self):
        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version]) + "workers/?health=Active",
        )
        assert len(data["results"]) == 2  # nosec - unit test support

        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version]) + "workers/?state=Online",
        )
        assert len(data["results"]) == 1  # nosec - unit test support

        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version]) + "workers/?hostname=worker1",
        )
        assert len(data["results"]) == 1  # nosec - unit test support

    def test_workers_update_unauthorized(self):
        response = self.userclient.put(
            reverse("api-root", args=[self.version]) + "workers/worker2/",
            {"health": "Active"},
        )
        assert response.status_code == 403  # nosec - unit test support

    def test_workers_update(self):
        # Set health
        response = self.adminclient.put(
            reverse("api-root", args=[self.version]) + "workers/worker2/",
            {"health": "Active"},
        )
        assert response.status_code == 200  # nosec - unit test support
        content = json.loads(response.content.decode("utf-8"))
        assert content["health"] == "Active"  # nosec - unit test support
        assert Worker.objects.get(hostname="worker2").get_health_display() == "Active"
        assert LogEntry.objects.filter(object_id="worker2").count() == 1
        assert LogEntry.objects.get(object_id="worker2").user == self.admin
        assert (
            LogEntry.objects.get(object_id="worker2").change_message
            == "Maintenance → Active"
        )

    def test_aliases_list(self):
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version]) + "aliases/?ordering=name",
        )
        # We have 4 aliases, but only 2 are visible
        assert len(data["results"]) == 2  # nosec - unit test support
        assert data["results"][0]["name"] == "test1"  # nosec - unit test support
        assert data["results"][1]["name"] == "test2"  # nosec - unit test support

    def test_aliases_retrieve(self):
        data = self.hit(
            self.userclient, reverse("api-root", args=[self.version]) + "aliases/test1/"
        )
        assert data["name"] == "test1"  # nosec - unit test support
        assert data["device_type"] == "public_device_type1"  # nosec - unit test support

    def test_aliases_create_unauthorized(self):
        response = self.userclient.post(
            reverse("api-root", args=[self.version]) + "aliases/",
            {"name": "test5", "device_type": "qemu"},
        )
        assert response.status_code == 403  # nosec - unit test support

    def test_aliases_create(self):
        response = self.adminclient.post(
            reverse("api-root", args=[self.version]) + "aliases/",
            {"name": "test5", "device_type": "public_device_type1"},
        )
        assert response.status_code == 201  # nosec - unit test support

    def test_aliases_delete_unauthorized(self):
        response = self.userclient.delete(
            reverse("api-root", args=[self.version]) + "aliases/test2/"
        )
        assert response.status_code == 403  # nosec - unit test support

    def test_aliases_delete(self):
        response = self.adminclient.delete(
            reverse("api-root", args=[self.version]) + "aliases/test2/"
        )
        assert response.status_code == 204  # nosec - unit test support

    def test_aliases_filters(self):
        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version]) + "aliases/?name=test2",
        )
        assert len(data["results"]) == 1  # nosec - unit test support

        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version]) + "aliases/?name__in=test1,test2",
        )
        assert len(data["results"]) == 2  # nosec - unit test support

        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version]) + "aliases/?name__contains=2",
        )
        assert len(data["results"]) == 1  # nosec - unit test support

    def test_submit_no_authentication(self):
        response = self.userclient_no_token.post(
            reverse("api-root", args=[self.version]) + "jobs/",
            {"definition": EXAMPLE_JOB},
        )
        assert response.status_code == 403  # nosec - unit test support

    def test_submit_unauthorized(self):
        response = self.userclient.post(
            reverse("api-root", args=[self.version]) + "jobs/",
            {"definition": EXAMPLE_WORKING_JOB_RESTRICTED_DEVICE_TYPE},
        )
        assert response.status_code == 400  # nosec - unit test support
        msg = json.loads(response.content)
        assert (
            msg["message"]
            == "Devices unavailable: Device type 'restricted_device_type1' is unavailable to user 'user1'"
        )

    def test_submit_authenticated(self):
        response = self.userclient.post(
            reverse("api-root", args=[self.version]) + "jobs/",
            {"definition": EXAMPLE_WORKING_JOB},
            format="json",
        )
        assert response.status_code == 201  # nosec - unit test support
        assert TestJob.objects.count() == 3  # nosec - unit test support

    def test_submit_bad_request_no_device_type(self):
        response = self.adminclient.post(
            reverse("api-root", args=[self.version]) + "jobs/",
            {"definition": EXAMPLE_JOB},
            format="json",
        )
        assert response.status_code == 400  # nosec - unit test support
        content = json.loads(response.content.decode("utf-8"))
        assert (
            content["message"] == "job submission failed: 'device_type'."
        )  # nosec - unit test support

    def test_submit_admin(self):
        response = self.adminclient.post(
            reverse("api-root", args=[self.version]) + "jobs/",
            {"definition": EXAMPLE_WORKING_JOB},
            format="json",
        )
        assert response.status_code == 201  # nosec - unit test support
        assert TestJob.objects.count() == 3  # nosec - unit test support

    def test_resubmit_unauthorized(self):
        response = self.userclient.post(
            reverse("api-root", args=[self.version])
            + "jobs/%s/resubmit/" % self.private_testjob1.id
        )
        assert response.status_code == 404  # nosec - unit test support

    def test_resubmit(self):
        response = self.adminclient.post(
            reverse("api-root", args=[self.version])
            + "jobs/%s/resubmit/" % self.public_testjob1.id
        )
        assert response.status_code == 201  # nosec - unit test support
        assert TestJob.objects.count() == 3  # nosec - unit test support

    def test_cancel(self, mocker):
        mocker.patch("lava_scheduler_app.models.TestJob.cancel")
        response = self.adminclient.get(
            reverse("api-root", args=[self.version])
            + "jobs/%s/cancel/" % self.public_testjob1.id
        )
        assert response.status_code == 200  # nosec - unit test support
        msg = json.loads(response.content)
        assert msg["message"] == "Job cancel signal sent."  # nosec - unit test support

    def test_tags_list(self):
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version]) + "tags/?ordering=name",
        )
        assert len(data["results"]) == 2  # nosec - unit test support
        assert data["results"][0]["name"] == "tag1"  # nosec - unit test support
        assert data["results"][1]["name"] == "tag2"  # nosec - unit test support

    def test_tags_retrieve(self):
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version]) + "tags/%s/" % self.tag1.id,
        )
        assert data["name"] == "tag1"  # nosec - unit test support
        assert data["description"] == "description1"  # nosec - unit test support

    def test_tags_create_unauthorized(self):
        response = self.userclient.post(
            reverse("api-root", args=[self.version]) + "tags/",
            {"name": "tag3", "description": "description3"},
        )
        assert response.status_code == 403  # nosec - unit test support

    def test_tags_create(self):
        response = self.adminclient.post(
            reverse("api-root", args=[self.version]) + "tags/",
            {"name": "tag3", "description": "description3"},
        )
        assert response.status_code == 201  # nosec - unit test support

    def test_tags_delete_unauthorized(self):
        response = self.userclient.delete(
            reverse("api-root", args=[self.version]) + "tags/%s/" % self.tag2.id
        )
        assert response.status_code == 403  # nosec - unit test support

    def test_tags_delete(self):
        response = self.adminclient.delete(
            reverse("api-root", args=[self.version]) + "tags/%s/" % self.tag2.id
        )
        assert response.status_code == 204  # nosec - unit test support

    def test_devicetype_permissions_list_unauthorized(self):
        response = self.userclient.get(
            reverse("api-root", args=[self.version]) + "permissions/devicetypes/"
        )
        assert response.status_code == 403  # nosec - unit test support

    def test_devicetype_permissions_list(self):
        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version])
            + "permissions/devicetypes/?ordering=id",
        )
        assert len(data["results"]) == 2  # nosec - unit test support
        assert (
            data["results"][0]["devicetype"] == "restricted_device_type1"
        )  # nosec - unit test support

    def test_devicetype_permissions_retrieve_unauthorized(self):
        response = self.userclient.get(
            reverse("api-root", args=[self.version]) + "permissions/devicetypes/1/"
        )
        assert response.status_code == 403  # nosec - unit test support

    def test_devicetype_permissions_retrieve(self):
        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version])
            + "permissions/devicetypes/%s/"
            % GroupDeviceTypePermission.objects.first().id,
        )
        assert (
            data["id"] == GroupDeviceTypePermission.objects.first().id
        )  # nosec - unit test support
        assert (
            data["devicetype"] == "restricted_device_type1"
        )  # nosec - unit test support

    def test_devicetype_permissions_create(self):
        response = self.adminclient.post(
            reverse("api-root", args=[self.version]) + "permissions/devicetypes/",
            {
                "group": "group1",
                "devicetype": "public_device_type1",
                "permission": "view_devicetype",
            },
        )
        assert response.status_code == 201  # nosec - unit test support

    def test_devicetype_permissions_delete_unauthorized(self):
        response = self.userclient.delete(
            reverse("api-root", args=[self.version])
            + "permissions/devicetypes/%s/"
            % GroupDeviceTypePermission.objects.first().id
        )
        assert response.status_code == 403  # nosec - unit test support

    def test_devicetype_permissions_delete(self):
        response = self.adminclient.delete(
            reverse("api-root", args=[self.version])
            + "permissions/devicetypes/%s/"
            % GroupDeviceTypePermission.objects.first().id
        )
        assert response.status_code == 204  # nosec - unit test support

    def test_device_permissions_list_unauthorized(self):
        response = self.userclient.get(
            reverse("api-root", args=[self.version]) + "permissions/devices/"
        )
        assert response.status_code == 403  # nosec - unit test support

    def test_device_permissions_list(self):
        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version])
            + "permissions/devices/?ordering=id",
        )
        assert len(data["results"]) == 2  # nosec - unit test support
        assert (
            data["results"][0]["device"] == "restricted_device1"
        )  # nosec - unit test support

    def test_device_permissions_retrieve_unauthorized(self):
        response = self.userclient.get(
            reverse("api-root", args=[self.version]) + "permissions/devices/1/"
        )
        assert response.status_code == 403  # nosec - unit test support

    def test_device_permissions_retrieve(self):
        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version])
            + "permissions/devices/%s/" % GroupDevicePermission.objects.first().id,
        )
        assert (
            data["id"] == GroupDevicePermission.objects.first().id
        )  # nosec - unit test support
        assert data["device"] == "restricted_device1"  # nosec - unit test support

    def test_device_permissions_create(self):
        response = self.adminclient.post(
            reverse("api-root", args=[self.version]) + "permissions/devices/",
            {"group": "group1", "device": "public01", "permission": "view_device"},
        )
        assert response.status_code == 201  # nosec - unit test support

    def test_device_permissions_delete_unauthorized(self):
        response = self.userclient.delete(
            reverse("api-root", args=[self.version])
            + "permissions/devices/%s/" % GroupDevicePermission.objects.first().id
        )
        assert response.status_code == 403  # nosec - unit test support

    def test_device_permissions_delete(self):
        response = self.adminclient.delete(
            reverse("api-root", args=[self.version])
            + "permissions/devices/%s/" % GroupDevicePermission.objects.first().id
        )
        assert response.status_code == 204  # nosec - unit test support

    def test_tags_filters(self):
        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version]) + "tags/?name=tag1",
        )
        assert len(data["results"]) == 1  # nosec - unit test support

        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version]) + "tags/?name__in=tag1,tag2",
        )
        assert len(data["results"]) == 2  # nosec - unit test support

        data = self.hit(
            self.adminclient,
            reverse("api-root", args=[self.version]) + "tags/?name__contains=2",
        )
        assert len(data["results"]) == 1  # nosec - unit test support

    def test_system_version(self):
        version = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version]) + "system/version/",
        )
        assert version["version"] == __version__
        response = self.userclient_no_token.get(
            reverse("api-root", args=[self.version]) + "system/version/"
        )
        assert response.status_code == 200  # nosec
        assert response.json()["version"] == __version__  # nosec

    def test_system_whoami(self):
        response = self.hit(
            self.userclient, reverse("api-root", args=[self.version]) + "system/whoami/"
        )
        assert response["user"] == self.user.username
        response = self.userclient_no_token.get(
            reverse("api-root", args=[self.version]) + "system/whoami/"
        )
        assert response.status_code == 200  # nosec
        assert response.json()["user"] == ""  # nosec

    def test_system_master_config(self):
        response = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version]) + "system/master_config/",
        )
        assert response["EVENT_SOCKET"] == settings.EVENT_SOCKET
        assert response["EVENT_TOPIC"] == settings.EVENT_TOPIC
        assert response["EVENT_NOTIFICATION"] == settings.EVENT_NOTIFICATION
        assert response["LOG_SIZE_LIMIT"] == settings.LOG_SIZE_LIMIT

        response = self.userclient_no_token.get(
            reverse("api-root", args=[self.version]) + "system/master_config/"
        )
        assert response.status_code == 200  # nosec

    def test_delete_not_authorized(self):
        response = self.userclient.delete(
            reverse("api-root", args=[self.version])
            + "jobs/%s/" % self.public_testjob1.id
        )
        assert response.status_code == 403  # nosec

    def test_delete_not_authenticated(self):
        response = self.userclient_no_token.delete(
            reverse("api-root", args=[self.version])
            + "jobs/%s/" % self.public_testjob1.id
        )
        assert response.status_code == 403  # nosec


def test_view_root(client):
    ret = client.get(reverse("api-root", args=[versions.versions[-1]]) + "?format=api")
    assert ret.status_code == 200


def test_view_devices(client, db):
    ret = client.get(
        reverse("api-root", args=[versions.versions[-1]]) + "devices/?format=api"
    )
    assert ret.status_code == 200


def test_view_devicetypes(client, db):
    ret = client.get(
        reverse("api-root", args=[versions.versions[-1]]) + "devicetypes/?format=api"
    )
    assert ret.status_code == 200


def test_view_jobs(client, db):
    ret = client.get(
        reverse("api-root", args=[versions.versions[-1]]) + "jobs/?format=api"
    )
    assert ret.status_code == 200


def test_view_workers(client, db):
    ret = client.get(
        reverse("api-root", args=[versions.versions[-1]]) + "workers/?format=api"
    )
    assert ret.status_code == 200
