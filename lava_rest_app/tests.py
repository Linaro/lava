# -*- coding: utf-8 -*-
# Copyright (C) 2018-2019 Linaro Limited
#
# Author: Milosz Wasilewski <milosz.wasilewski@linaro.org>
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

import json
import pytest
import tap
import yaml

from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from lava_scheduler_app.models import Device, DeviceType, TestJob, Worker
from lava_results_app import models as result_models
from linaro_django_xmlrpc.models import AuthToken

from . import versions


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

LOG_FILE = """
- {"dt": "2018-10-03T16:28:28.199903", "lvl": "info", "msg": "lava-dispatcher, installed at version: 2018.7-1+stretch"}
- {"dt": "2018-10-03T16:28:28.200807", "lvl": "info", "msg": "start: 0 validate"}
"""


class TestRestApi:
    @pytest.fixture(autouse=True)
    def setUp(self, db):
        self.version = versions.versions[-1]  # use latest version by default

        # create users
        self.admin = User.objects.create(username="admin", is_superuser=True)
        self.user = User.objects.create(username="user1")
        self.user_pwd = "supersecret"
        self.user.set_password(self.user_pwd)
        self.user.save()
        self.user_no_token_pwd = "secret"
        self.user_no_token = User.objects.create(username="user2")
        self.user_no_token.set_password(self.user_no_token_pwd)
        self.user_no_token.save()
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
        self.invisible_device_type1 = DeviceType.objects.create(
            name="invisible_device_type1", display=False
        )
        self.private_device_type1 = DeviceType.objects.create(
            name="private_device_type1", owners_only=True
        )

        # create devices
        self.public_device1 = Device.objects.create(
            hostname="public01",
            device_type=self.public_device_type1,
            worker_host=self.worker1,
        )
        self.private_device1 = Device.objects.create(
            hostname="private01",
            user=self.admin,
            is_public=False,
            device_type=self.private_device_type1,
            worker_host=self.worker1,
        )
        self.retired_device1 = Device.objects.create(
            hostname="retired01",
            device_type=self.public_device_type1,
            health=Device.HEALTH_RETIRED,
            worker_host=self.worker2,
        )

        # create testjobs
        self.public_testjob1 = TestJob.objects.create(
            definition=yaml.safe_dump(EXAMPLE_JOB),
            submitter=self.user,
            user=self.user,
            requested_device_type=self.public_device_type1,
            is_public=True,
            visibility=TestJob.VISIBLE_PUBLIC,
        )
        self.private_testjob1 = TestJob.objects.create(
            definition=yaml.safe_dump(EXAMPLE_JOB),
            submitter=self.admin,
            user=self.admin,
            requested_device_type=self.public_device_type1,
            is_public=False,
            visibility=TestJob.VISIBLE_PERSONAL,
        )
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

    def hit(self, client, url):
        response = client.get(url)
        assert response.status_code == 200  # nosec - unit test support
        if hasattr(response, "content"):
            text = response.content.decode("utf-8")
            if response["Content-Type"] == "application/json":
                return json.loads(text)
            return text
        return ""

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
        # only public test jobs should be available without logging in
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

    def test_testjob_logs(self, monkeypatch, tmpdir):
        (tmpdir / "output.yaml").write_text(LOG_FILE, encoding="utf-8")
        monkeypatch.setattr(TestJob, "output_dir", str(tmpdir))

        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/logs/" % self.public_testjob1.id,
        )

    def test_testjob_logs_offset(self, monkeypatch, tmpdir):
        (tmpdir / "output.yaml").write_text(LOG_FILE, encoding="utf-8")
        monkeypatch.setattr(TestJob, "output_dir", str(tmpdir))

        # use start=2 as log lines count start from 1
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/logs/?start=2" % self.public_testjob1.id,
        )
        # the value below depends on the log fragment used
        # be careful when changing either the value below or the log fragment
        assert len(data) == 82  # nosec - unit test support

    def test_testjob_logs_offset_end(self, monkeypatch, tmpdir):
        (tmpdir / "output.yaml").write_text(LOG_FILE, encoding="utf-8")
        monkeypatch.setattr(TestJob, "output_dir", str(tmpdir))

        # use start=2 as log lines count start from 1
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/logs/?start=1&end=2" % self.public_testjob1.id,
        )
        # the value below depends on the log fragment used
        # be careful when changing either the value below or the log fragment
        assert len(data) == 120  # nosec - unit test support

    def test_testjob_logs_bad_offset(self, monkeypatch, tmpdir):
        (tmpdir / "output.yaml").write_text(LOG_FILE, encoding="utf-8")
        monkeypatch.setattr(TestJob, "output_dir", str(tmpdir))

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

    def test_testjob_junit(self):
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/junit/" % self.public_testjob1.id,
        )
        lines = data.rstrip("\n").split("\n")
        assert len(lines) == 9  # nosec - unit test support
        assert (  # nosec - unit test support
            lines[0] == """<?xml version="1.0" encoding="utf-8"?>"""
        )
        assert (  # nosec - unit test support
            lines[1]
            == """<testsuites disabled="0" errors="1" failures="0" tests="2" time="0.0">"""
        )
        assert (  # nosec - unit test support
            lines[2]
            == """	<testsuite disabled="0" errors="1" failures="0" name="lava" skipped="0" tests="2" time="0">"""
        )
        assert lines[3].startswith(  # nosec - unit test support
            """		<testcase classname="lava" name="foo" timestamp="""
        )
        assert lines[3].endswith('">')  # nosec - unit test support
        assert (  # nosec - unit test support
            lines[4] == """			<error message="failed" type="error"/>"""
        )
        assert lines[5] == """		</testcase>"""  # nosec - unit test support
        assert lines[6].startswith(  # nosec - unit test support
            """		<testcase classname="lava" name="bar" timestamp="""
        )
        assert lines[6].endswith('"/>')  # nosec - unit test support
        assert lines[7] == """	</testsuite>"""  # nosec - unit test support
        assert lines[8] == """</testsuites>"""  # nosec - unit test support

    def test_testjob_tap13(self):
        data = self.hit(
            self.userclient,
            reverse("api-root", args=[self.version])
            + "jobs/%s/tap13/" % self.public_testjob1.id,
        )
        if hasattr(tap.tracker.Tracker, "set_plan"):
            assert (  # nosec - unit test support
                data
                == """TAP version 13
1..2
# TAP results for lava
not ok 1 foo
ok 2 bar
"""
            )
        else:
            assert (  # nosec - unit test support
                data
                == """# TAP results for lava
not ok 1 - foo
ok 2 - bar
"""
            )

    def test_devicetypes(self):
        data = self.hit(
            self.userclient, reverse("api-root", args=[self.version]) + "devicetypes/"
        )
        # only public device types should be available without logging in
        assert len(data["results"]) == 1  # nosec - unit test support

    def test_devices(self):
        data = self.hit(
            self.userclient, reverse("api-root", args=[self.version]) + "devices/"
        )
        # only public devices should be available without logging in
        assert len(data["results"]) == 1  # nosec - unit test support

    def test_devicetypes_admin(self):
        data = self.hit(
            self.adminclient, reverse("api-root", args=[self.version]) + "devicetypes/"
        )
        assert len(data["results"]) == 2  # nosec - unit test support

    def test_devices_admin(self):
        data = self.hit(
            self.adminclient, reverse("api-root", args=[self.version]) + "devices/"
        )
        assert len(data["results"]) == 2  # nosec - unit test support

    def test_workers(self):
        data = self.hit(
            self.userclient, reverse("api-root", args=[self.version]) + "workers/"
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
