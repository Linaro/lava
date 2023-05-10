# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import datetime
import os

from lava_common.exceptions import InfrastructureError, JobError
from lava_common.timeout import Timeout
from lava_common.yaml import yaml_safe_dump, yaml_safe_load
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.testdef import get_test_action_namespaces
from lava_dispatcher.actions.test.shell import TestShellAction, TestShellRetry
from lava_dispatcher.device import NewDevice
from lava_dispatcher.job import Job
from lava_dispatcher.parser import JobParser
from lava_dispatcher.protocols.multinode import MultinodeProtocol
from lava_dispatcher.protocols.vland import VlandProtocol
from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase
from tests.utils import DummyLogger


class TestDefinitionHandlers(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.factory = Factory()
        self.job = self.factory.create_kvm_job("sample_jobs/kvm.yaml")

    def test_testshell(self):
        testshell = None
        for action in self.job.pipeline.actions:
            self.assertIsNotNone(action.name)
            if isinstance(action, TestShellRetry):
                testshell = action.pipeline.actions[0]
                break
        self.assertIsInstance(testshell, TestShellAction)
        self.assertTrue(testshell.valid)

        if "timeout" in testshell.parameters:
            time_int = Timeout.parse(testshell.parameters["timeout"])
        else:
            time_int = Timeout.default_duration()
        self.assertEqual(
            datetime.timedelta(seconds=time_int).total_seconds(),
            testshell.timeout.duration,
        )

    def test_missing_handler(self):
        (rendered, _) = self.factory.create_device("kvm01.jinja2")
        device = NewDevice(yaml_safe_load(rendered))
        kvm_yaml = os.path.join(os.path.dirname(__file__), "sample_jobs/kvm.yaml")
        parser = JobParser()
        with open(kvm_yaml) as sample_job_data:
            data = yaml_safe_load(sample_job_data)
        data["actions"][2]["test"]["definitions"][0]["from"] = "unusable-handler"
        try:
            job = parser.parse(yaml_safe_dump(data), device, 4212, None, "")
            job.logger = DummyLogger()
        except JobError:
            pass
        except Exception as exc:
            self.fail(exc)
        else:
            self.fail("JobError not raised")

    def test_eventpatterns(self):
        testshell = None
        for action in self.job.pipeline.actions:
            self.assertIsNotNone(action.name)
            if isinstance(action, TestShellRetry):
                testshell = action.pipeline.actions[0]
                break
        self.assertTrue(testshell.valid)
        self.assertFalse(testshell.check_patterns("exit", None, ""))
        self.assertRaises(
            InfrastructureError, testshell.check_patterns, "eof", None, ""
        )
        self.assertTrue(testshell.check_patterns("timeout", None, ""))


class X86Factory(Factory):
    def create_x86_job(self, filename, device, validate=True):
        return self.create_job(device, filename, validate=validate)


class TestMultiNodeOverlay(StdoutTestCase):
    def setUp(self):
        super().setUp()
        factory = X86Factory()
        self.server_job = factory.create_x86_job(
            "sample_jobs/test_action-1.yaml", "lng-generator-01.jinja2", validate=False
        )
        self.client_job = factory.create_x86_job(
            "sample_jobs/test_action-2.yaml", "lng-generator-02.jinja2", validate=False
        )

    def test_action_namespaces(self):
        self.assertIsNotNone(self.server_job)
        self.assertIsNotNone(self.client_job)
        deploy_server = [
            action
            for action in self.server_job.pipeline.actions
            if action.name == "tftp-deploy"
        ][0]
        self.assertIn(MultinodeProtocol.name, deploy_server.parameters.keys())
        self.assertIn(VlandProtocol.name, deploy_server.parameters.keys())
        self.assertEqual(
            ["common"], get_test_action_namespaces(self.server_job.parameters)
        )
        namespace = self.server_job.parameters.get("namespace")
        self.assertIsNone(namespace)
        namespace = self.client_job.parameters.get("namespace")
        self.assertIsNone(namespace)
        deploy_client = [
            action
            for action in self.client_job.pipeline.actions
            if action.name == "tftp-deploy"
        ][0]
        self.assertIn(MultinodeProtocol.name, deploy_client.parameters.keys())
        self.assertIn(VlandProtocol.name, deploy_client.parameters.keys())
        key_list = []
        for block in self.client_job.parameters["actions"]:
            key_list.extend(block.keys())
        self.assertEqual(key_list, ["deploy", "boot", "test"])  # order is important
        self.assertEqual(
            ["common"], get_test_action_namespaces(self.client_job.parameters)
        )
        key_list = []
        for block in self.server_job.parameters["actions"]:
            key_list.extend(block.keys())
        self.assertEqual(key_list, ["deploy", "boot", "test"])  # order is important


class TestShellResults(StdoutTestCase):
    class FakeJob(Job):
        pass

    class FakeDeploy:
        """
        Derived from object, *not* Deployment as this confuses python -m unittest discover
        - leads to the FakeDeploy being called instead.
        """

        def __init__(self, parent):
            self.__parameters__ = {}
            self.pipeline = parent
            self.job = parent.job
            self.action = TestShellResults.FakeAction()

    class FakePipeline(Pipeline):
        def __init__(self, parent=None, job=None):
            super().__init__(parent, job)

    class FakeAction(Action):
        """
        Isolated Action which can be used to generate artificial exceptions.
        """

        name = "fake-action"
        description = "fake, do not use outside unit tests"
        summary = "fake action for unit tests"

        def __init__(self):
            super().__init__()
            self.count = 1

        def run(self, connection, max_end_time):
            self.count += 1
            raise JobError("fake error")
