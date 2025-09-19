# Copyright (C) 2016 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import unittest

from lava_common.exceptions import JobError
from lava_dispatcher.actions.boot.lxc import BootLxcAction, LxcAddStaticDevices
from lava_dispatcher.actions.deploy.lxc import LxcAction, LxcCreateAction
from lava_dispatcher.actions.deploy.testdef import (
    TestDefinitionAction,
    TestRunnerAction,
)
from lava_dispatcher.actions.deploy.tftp import TftpAction
from lava_dispatcher.actions.test.shell import TestShellAction, TestShellRetry
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase
from tests.utils import infrastructure_error


class LxcFactory(Factory):
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    def create_lxc_job(self, filename):
        return self.create_job("lxc-01", filename)

    def create_bbb_lxc_job(self, filename):
        return self.create_job("bbb-01", filename)

    def create_adb_nuc_job(self, filename):
        return self.create_job("adb-nuc-01", filename)

    def create_hikey_aep_job(self, filename):
        return self.create_job("hi6220-hikey-r2-01", filename)


class TestLxcDeploy(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        factory = LxcFactory()
        self.job = factory.create_lxc_job("sample_jobs/lxc.yaml")

    def test_deploy_job(self):
        self.assertEqual(self.job.pipeline.job, self.job)
        for action in self.job.pipeline.actions:
            self.assertEqual(action.job, self.job)

    def test_pipeline(self):
        description_ref = self.pipeline_reference("lxc.yaml", job=self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe())

    @unittest.skipIf(infrastructure_error("lxc-create"), "lxc-create not installed")
    def test_validate(self):
        try:
            self.job.pipeline.validate_actions()
        except JobError as exc:
            self.fail(exc)
        for action in self.job.pipeline.actions:
            self.assertEqual([], action.errors)

    @unittest.skipIf(infrastructure_error("lxc-create"), "lxc-create not installed")
    def test_create(self):
        self.job.validate()
        action = self.job.pipeline.find_action(LxcCreateAction)

        self.assertEqual(
            action.lxc_data["lxc_name"], f"pipeline-lxc-test-{self.job.job_id}"
        )
        self.assertEqual(action.lxc_data["lxc_distribution"], "debian")
        self.assertEqual(action.lxc_data["lxc_release"], "sid")
        self.assertEqual(action.lxc_data["lxc_template"], "debian")
        self.assertEqual(
            action.lxc_data["lxc_mirror"], "http://ftp.us.debian.org/debian/"
        )
        self.assertEqual(
            action.lxc_data["lxc_security_mirror"],
            "http://mirror.csclub.uwaterloo.ca/debian-security/",
        )

    @unittest.skipIf(infrastructure_error("lxc-start"), "lxc-start not installed")
    def test_boot(self):
        action = self.job.pipeline.actions[1]
        # get the action & populate it
        self.assertEqual(action.parameters["method"], "lxc")
        self.assertEqual(action.parameters["prompts"], ["root@(.*):/#"])

    def test_testdefinitions(self):
        for action in self.job.pipeline.actions:
            if action.name == "test":
                # get the action & populate it
                self.assertEqual(len(action.parameters["definitions"]), 2)


class TestLxcWithDevices(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.factory = LxcFactory()
        self.job = self.factory.create_bbb_lxc_job("sample_jobs/bbb-lxc.yaml")

    @unittest.skipIf(infrastructure_error("lxc-start"), "lxc-start not installed")
    def test_lxc_feedback(self):
        self.assertIsNotNone(self.job)
        # validate with two test actions, lxc and device
        self.job.validate()

        drone_test = self.job.pipeline.find_action(TestShellRetry)
        self.assertNotEqual(10, drone_test.connection_timeout.duration)

        drone_shell = drone_test.pipeline.find_action(TestShellAction)
        self.assertEqual(10, drone_shell.connection_timeout.duration)

    @unittest.skipIf(infrastructure_error("lxc-start"), "lxc-start not installed")
    def test_lxc_with_device(self):
        self.assertIsNotNone(self.job)
        # validate with two test actions, lxc and device
        self.job.validate()

        lxc_deploy = self.job.pipeline.find_action(LxcAction)
        lxc_test_def = lxc_deploy.pipeline.find_action(TestDefinitionAction)
        self.assertIsNotNone(lxc_test_def.level, lxc_test_def.test_list)
        lxc_runner = lxc_test_def.pipeline.find_action(TestRunnerAction)
        self.assertIsNotNone(lxc_runner.testdef_levels)

        tftp_deploy = self.job.pipeline.find_action(TftpAction)
        tftp_test_def = tftp_deploy.pipeline.find_action(TestDefinitionAction)
        namespace = tftp_test_def.parameters.get("namespace")
        self.assertIsNotNone(namespace)
        test_actions = [
            action for action in self.job.parameters["actions"] if "test" in action
        ]
        for action in test_actions:
            if "namespace" in action["test"]:
                if action["test"]["namespace"] == namespace:
                    self.assertEqual(
                        action["test"]["definitions"][0]["name"], "smoke-tests-bbb"
                    )
        namespace_tests = [
            action["test"]["definitions"]
            for action in test_actions
            if "namespace" in action["test"]
            and action["test"]["namespace"] == namespace
        ]
        self.assertEqual(len(namespace_tests), 1)
        self.assertEqual(len(test_actions), 2)
        self.assertEqual("smoke-tests-bbb", namespace_tests[0][0]["name"])
        self.assertEqual("smoke-tests-bbb", tftp_test_def.test_list[0][0]["name"])
        self.assertIsNotNone(tftp_test_def.level, tftp_test_def.test_list)
        tftp_runner = tftp_test_def.pipeline.find_action(TestRunnerAction)
        self.assertIsNotNone(tftp_runner.testdef_levels)

        lxc2_deploy = self.job.pipeline.find_action(LxcAction)
        lxc2_test_def = lxc2_deploy.pipeline.find_action(TestDefinitionAction)
        self.assertIsNotNone(lxc2_test_def.level, lxc2_test_def.test_list)
        lxc2_runner = lxc2_test_def.pipeline.find_action(TestRunnerAction)
        self.assertIsNotNone(lxc2_runner.testdef_levels)

    @unittest.skipIf(infrastructure_error("lxc-start"), "lxc-start not installed")
    def test_lxc_with_static_device(self):
        self.job = self.factory.create_hikey_aep_job("sample_jobs/hi6220-hikey.yaml")
        self.job.validate()

        lxc_static = self.job.pipeline.find_action(LxcAddStaticDevices)
        self.assertIsNotNone(lxc_static)
        self.assertIsInstance(self.job.device.get("static_info"), list)
        self.assertEqual(len(self.job.device.get("static_info")), 1)
        for board in self.job.device.get("static_info"):
            self.assertIsInstance(board, dict)
            self.assertIn("board_id", board)
            self.assertEqual(board["board_id"], "S_N0123456")
        description_ref = self.pipeline_reference("hi6220-hikey.yaml", job=self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe())

    @unittest.skipIf(infrastructure_error("lxc-start"), "lxc-start not installed")
    def test_lxc_without_lxctest(self):
        job = self.factory.create_job("bbb-01", "sample_jobs/bbb-lxc-notest.yaml")

        lxc_deploy = job.pipeline.find_action(LxcAction)
        names = [action.name for action in lxc_deploy.pipeline.actions]
        self.assertNotIn("prepare-tftp-overlay", names)
        namespace1 = lxc_deploy.parameters.get("namespace")

        tftp_deploy = job.pipeline.find_action(TftpAction)
        test_def = tftp_deploy.pipeline.find_action(TestDefinitionAction)
        namespace = test_def.parameters.get("namespace")
        self.assertIsNotNone(namespace)
        self.assertIsNotNone(namespace1)
        self.assertNotEqual(namespace, namespace1)
        self.assertNotEqual(self.job.pipeline.describe(), job.pipeline.describe())
        test_actions = [
            action for action in job.parameters["actions"] if "test" in action
        ]
        for action in test_actions:
            if "namespace" in action["test"]:
                if action["test"]["namespace"] == namespace:
                    self.assertEqual(
                        action["test"]["definitions"][0]["name"], "smoke-tests-bbb"
                    )
            else:
                self.fail("Found a test action not from the tftp boot")
        namespace_tests = [
            action["test"]["definitions"]
            for action in test_actions
            if "namespace" in action["test"]
            and action["test"]["namespace"] == namespace
        ]
        self.assertEqual(len(namespace_tests), 1)
        self.assertEqual(len(test_actions), 1)

        description_ref = self.pipeline_reference("bbb-lxc-notest.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

    def test_adb_nuc_job(self):
        self.factory = LxcFactory()
        job = self.factory.create_adb_nuc_job("sample_jobs/adb-nuc.yaml")
        description_ref = self.pipeline_reference("adb-nuc.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

    @unittest.skipIf(infrastructure_error("lxc-start"), "lxc-start not installed")
    def test_iot_lxc(self):
        self.factory = Factory()
        job = self.factory.create_job("frdm-k64f-01", "sample_jobs/frdm-k64f-lxc.yaml")
        job.validate()

        description_ref = self.pipeline_reference("frdm-k64f-lxc.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

        job.pipeline.find_action(LxcAction)
        job.pipeline.find_action(BootLxcAction)
