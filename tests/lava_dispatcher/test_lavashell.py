# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import datetime
from typing import Any

from lava_common.exceptions import InfrastructureError, JobError
from lava_common.timeout import Timeout
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.testdef import get_test_action_namespaces
from lava_dispatcher.actions.deploy.tftp import TftpAction
from lava_dispatcher.actions.test.shell import TestShellAction
from lava_dispatcher.job import Job
from lava_dispatcher.protocols.multinode import MultinodeProtocol
from lava_dispatcher.protocols.vland import VlandProtocol
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase


class TestDefinitionHandlers(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.factory = Factory()

    def test_testshell(self):
        job = self.factory.create_kvm_job("sample_jobs/kvm.yaml")

        testshell = job.pipeline.find_action(TestShellAction)

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
        def set_test_from_to_bad_value(job_dict: dict[str, Any]) -> None:
            job_dict["actions"][-1]["test"]["definitions"][0][
                "from"
            ] = "unusable-handler-test"

        with self.assertRaisesRegex(
            JobError,
            "(?=No testdef_repo handler is available for)"
            "(?=.*unusable-handler-test)",
        ):
            self.factory.create_job(
                "kvm01",
                "sample_jobs/kvm.yaml",
                validate=False,
                job_dict_preprocessor=set_test_from_to_bad_value,
            )

    def test_eventpatterns(self):
        job = self.factory.create_kvm_job("sample_jobs/kvm.yaml")

        testshell = job.pipeline.find_action(TestShellAction)

        self.assertTrue(testshell.valid)
        self.assertFalse(testshell.check_patterns("exit", None))
        self.assertRaises(InfrastructureError, testshell.check_patterns, "eof", None)
        self.assertTrue(testshell.check_patterns("timeout", None))


class X86Factory(Factory):
    def create_x86_job(self, filename, device, validate=True):
        return self.create_job(device, filename, validate=validate)


class TestMultiNodeOverlay(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        factory = Factory()
        self.server_job = factory.create_job(
            "lng-generator-01",
            "sample_jobs/test_action-1.yaml",
            validate=False,
        )
        self.client_job = factory.create_job(
            "lng-generator-02",
            "sample_jobs/test_action-2.yaml",
            validate=False,
        )

    def test_action_namespaces(self):
        self.assertIsNotNone(self.server_job)
        self.assertIsNotNone(self.client_job)

        deploy_server = self.server_job.pipeline.find_action(TftpAction)
        self.assertIn(MultinodeProtocol.name, deploy_server.parameters.keys())
        self.assertIn(VlandProtocol.name, deploy_server.parameters.keys())
        self.assertEqual(
            ["common"], get_test_action_namespaces(self.server_job.parameters)
        )
        namespace = self.server_job.parameters.get("namespace")
        self.assertIsNone(namespace)
        namespace = self.client_job.parameters.get("namespace")
        self.assertIsNone(namespace)

        deploy_client = self.client_job.pipeline.find_action(TftpAction)
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


class TestShellResults(LavaDispatcherTestCase):
    class FakeJob(Job):
        pass

    class FakeDeploy:
        """
        Derived from object, *not* Deployment as this confuses
        python -m unittest discover
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
