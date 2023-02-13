# Copyright (C) 2016 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import unittest

from lava_common.exceptions import JobError
from lava_common.yaml import yaml_safe_dump, yaml_safe_load
from lava_dispatcher.actions.deploy.lxc import LxcCreateAction
from lava_dispatcher.device import NewDevice
from lava_dispatcher.parser import JobParser
from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase
from tests.utils import DummyLogger, infrastructure_error


class LxcFactory(Factory):
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    def create_lxc_job(self, filename):
        return self.create_job("lxc-01.jinja2", filename)

    def create_bbb_lxc_job(self, filename):
        return self.create_job("bbb-01.jinja2", filename)

    def create_adb_nuc_job(self, filename):
        return self.create_job("adb-nuc-01.jinja2", filename)

    def create_hikey_aep_job(self, filename):
        job = super().create_job("hi6220-hikey-r2-01.jinja2", filename)
        job.logger = DummyLogger()
        return job


class TestLxcDeploy(StdoutTestCase):
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
        for action in self.job.pipeline.actions:
            if isinstance(action, LxcCreateAction):
                self.assertEqual(action.lxc_data["lxc_name"], "pipeline-lxc-test-4577")
                self.assertEqual(action.lxc_data["lxc_distribution"], "debian")
                self.assertEqual(action.lxc_data["lxc_release"], "sid")
                self.assertEqual(action.lxc_data["lxc_arch"], "amd64")
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


class TestLxcWithDevices(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.factory = LxcFactory()
        self.job = self.factory.create_bbb_lxc_job("sample_jobs/bbb-lxc.yaml")

    @unittest.skipIf(infrastructure_error("lxc-start"), "lxc-start not installed")
    def test_lxc_feedback(self):
        self.assertIsNotNone(self.job)
        # validate with two test actions, lxc and device
        self.job.validate()
        drone_test = [
            action
            for action in self.job.pipeline.actions
            if action.name == "lava-test-retry"
        ][0]
        self.assertNotEqual(10, drone_test.connection_timeout.duration)
        drone_shell = [
            action
            for action in drone_test.pipeline.actions
            if action.name == "lava-test-shell"
        ][0]
        self.assertEqual(10, drone_shell.connection_timeout.duration)

    @unittest.skipIf(infrastructure_error("lxc-start"), "lxc-start not installed")
    def test_lxc_with_device(self):
        self.assertIsNotNone(self.job)
        # validate with two test actions, lxc and device
        self.job.validate()
        lxc_yaml = os.path.join(os.path.dirname(__file__), "sample_jobs/bbb-lxc.yaml")
        with open(lxc_yaml) as sample_job_data:
            data = yaml_safe_load(sample_job_data)
        lxc_deploy = [
            action
            for action in self.job.pipeline.actions
            if action.name == "lxc-deploy"
        ][0]
        overlay = [
            action
            for action in lxc_deploy.pipeline.actions
            if action.name == "lava-overlay"
        ][0]
        test_def = [
            action
            for action in overlay.pipeline.actions
            if action.name == "test-definition"
        ][0]
        self.assertIsNotNone(test_def.level, test_def.test_list)
        runner = [
            action
            for action in test_def.pipeline.actions
            if action.name == "test-runscript-overlay"
        ][0]
        self.assertIsNotNone(runner.testdef_levels)
        tftp_deploy = [
            action
            for action in self.job.pipeline.actions
            if action.name == "tftp-deploy"
        ][0]
        prepare = [
            action
            for action in tftp_deploy.pipeline.actions
            if action.name == "prepare-tftp-overlay"
        ][0]
        overlay = [
            action
            for action in prepare.pipeline.actions
            if action.name == "lava-overlay"
        ][0]
        test_def = [
            action
            for action in overlay.pipeline.actions
            if action.name == "test-definition"
        ][0]
        namespace = test_def.parameters.get("namespace")
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
        self.assertEqual("smoke-tests-bbb", test_def.test_list[0][0]["name"])
        self.assertIsNotNone(test_def.level, test_def.test_list)
        runner = [
            action
            for action in test_def.pipeline.actions
            if action.name == "test-runscript-overlay"
        ][0]
        self.assertIsNotNone(runner.testdef_levels)
        # remove the second test action
        data["actions"].pop()
        test_actions = [action for action in data["actions"] if "test" in action]
        self.assertEqual(len(test_actions), 1)
        self.assertEqual(test_actions[0]["test"]["namespace"], "probe")
        parser = JobParser()
        (rendered, _) = self.factory.create_device("bbb-01.jinja2")
        device = NewDevice(yaml_safe_load(rendered))
        job = parser.parse(yaml_safe_dump(data), device, 4577, None, "")
        job.logger = DummyLogger()
        job.validate()
        lxc_deploy = [
            action
            for action in self.job.pipeline.actions
            if action.name == "lxc-deploy"
        ][0]
        overlay = [
            action
            for action in lxc_deploy.pipeline.actions
            if action.name == "lava-overlay"
        ][0]
        test_def = [
            action
            for action in overlay.pipeline.actions
            if action.name == "test-definition"
        ][0]
        self.assertIsNotNone(test_def.level, test_def.test_list)
        runner = [
            action
            for action in test_def.pipeline.actions
            if action.name == "test-runscript-overlay"
        ][0]
        self.assertIsNotNone(runner.testdef_levels)

    @unittest.skipIf(infrastructure_error("lxc-start"), "lxc-start not installed")
    def test_lxc_with_static_device(self):
        self.job = self.factory.create_hikey_aep_job("sample_jobs/hi6220-hikey.yaml")
        self.job.validate()
        lxc_boot = [
            action for action in self.job.pipeline.actions if action.name == "lxc-boot"
        ][0]
        lxc_static = [
            action
            for action in lxc_boot.pipeline.actions
            if action.name == "lxc-add-static"
        ][0]
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
        lxc_yaml = os.path.join(
            os.path.dirname(__file__), "sample_jobs/bbb-lxc-notest.yaml"
        )
        with open(lxc_yaml) as sample_job_data:
            data = yaml_safe_load(sample_job_data)
        parser = JobParser()
        (rendered, _) = self.factory.create_device("bbb-01.jinja2")
        device = NewDevice(yaml_safe_load(rendered))
        job = parser.parse(yaml_safe_dump(data), device, 4577, None, "")
        job.logger = DummyLogger()
        job.validate()
        lxc_deploy = [
            action for action in job.pipeline.actions if action.name == "lxc-deploy"
        ][0]
        names = [action.name for action in lxc_deploy.pipeline.actions]
        self.assertNotIn("prepare-tftp-overlay", names)
        namespace1 = lxc_deploy.parameters.get("namespace")
        tftp_deploy = [
            action for action in job.pipeline.actions if action.name == "tftp-deploy"
        ][0]
        prepare = [
            action
            for action in tftp_deploy.pipeline.actions
            if action.name == "prepare-tftp-overlay"
        ][0]
        overlay = [
            action
            for action in prepare.pipeline.actions
            if action.name == "lava-overlay"
        ][0]
        test_def = [
            action
            for action in overlay.pipeline.actions
            if action.name == "test-definition"
        ][0]
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
        job = self.factory.create_job(
            "frdm-k64f-01.jinja2", "sample_jobs/frdm-k64f-lxc.yaml"
        )
        job.validate()
        self.assertIsNotNone(
            [action for action in job.pipeline.actions if action.name == "lxc-deploy"]
        )
        self.assertIsNotNone(
            [action for action in job.pipeline.actions if action.name == "lxc-boot"]
        )
        description_ref = self.pipeline_reference("frdm-k64f-lxc.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
