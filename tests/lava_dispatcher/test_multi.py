# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


import os
from unittest.mock import patch

from lava_common.decorators import nottest
from lava_common.yaml import yaml_safe_dump, yaml_safe_load
from lava_dispatcher.action import Action, Pipeline, Timeout
from lava_dispatcher.device import NewDevice
from lava_dispatcher.job import Job
from lava_dispatcher.parser import JobParser
from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase
from tests.lava_dispatcher.test_uboot import UBootFactory
from tests.utils import DummyLogger


class TestMultiDeploy(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.parameters = {}
        self.parsed_data = {  # fake parsed YAML
            "device_type": "fake",
            "job_name": "fake_job",
            "timeouts": {"job": {"minutes": 2}},
            "priority": "medium",
            "actions": [
                {
                    "deploy": {
                        "namespace": "common",
                        "to": "fake_to",
                        "example": "nowhere",
                    }
                },
                {
                    "deploy": {
                        "namespace": "common",
                        "to": "destination",
                        "parameters": "faked",
                    }
                },
                {
                    "deploy": {
                        "namespace": "common",
                        "to": "tftp",
                        "parameters": "valid",
                    }
                },
            ],
        }

    class FakeDevice(NewDevice):
        def check_config(self, job):
            pass

        def __init__(self):
            data = yaml_safe_load(Factory().create_device("bbb-01.jinja2")[0])
            super().__init__(data)

    @nottest
    class TestDeploy:  # cannot be a subclass of Deployment without a full select function.
        def __init__(self, parent, parameters, job):
            super().__init__()
            self.action = TestMultiDeploy.TestDeployAction()
            self.action.job = job
            self.action.section = "internal"
            parent.add_action(self.action, parameters)

    class TestDeployAction(Action):
        name = "fake-deploy"
        description = "fake for tests only"
        summary = "fake deployment"

        def run(self, connection, max_end_time):
            self.data[self.name] = self.parameters
            return connection  # no actual connection during this fake job

    @nottest
    class TestJob(Job):
        def __init__(self):
            super().__init__(4122, 0, self.parameters)

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_multi_deploy(self, which_mock):
        self.assertIsNotNone(self.parsed_data)
        job = Job(4212, self.parsed_data, None)
        job.timeout = Timeout("Job", Timeout.parse({"minutes": 2}))
        pipeline = Pipeline(job=job)
        device = TestMultiDeploy.FakeDevice()
        self.assertIsNotNone(device)
        job.device = device
        job.logger = DummyLogger()
        job.pipeline = pipeline
        counts = {}
        for action_data in self.parsed_data["actions"]:
            for name in action_data:
                counts.setdefault(name, 1)
                parameters = action_data[name]
                test_deploy = TestMultiDeploy.TestDeploy(pipeline, parameters, job)
                self.assertEqual({}, test_deploy.action.data)
                counts[name] += 1
        # check that only one action has the example set
        self.assertEqual(
            ["nowhere"],
            [
                detail["deploy"]["example"]
                for detail in self.parsed_data["actions"]
                if "example" in detail["deploy"]
            ],
        )
        self.assertEqual(
            ["faked", "valid"],
            [
                detail["deploy"]["parameters"]
                for detail in self.parsed_data["actions"]
                if "parameters" in detail["deploy"]
            ],
        )
        self.assertIsInstance(pipeline.actions[0], TestMultiDeploy.TestDeployAction)
        self.assertIsInstance(pipeline.actions[1], TestMultiDeploy.TestDeployAction)
        self.assertIsInstance(pipeline.actions[2], TestMultiDeploy.TestDeployAction)
        job.validate()
        self.assertEqual([], job.pipeline.errors)
        job.run()
        self.assertNotEqual(
            pipeline.actions[0].data, {"fake-deploy": pipeline.actions[0].parameters}
        )
        self.assertEqual(
            pipeline.actions[1].data, {"fake-deploy": pipeline.actions[2].parameters}
        )
        # check that values from previous DeployAction run actions have been cleared
        self.assertEqual(
            pipeline.actions[2].data, {"fake-deploy": pipeline.actions[2].parameters}
        )


class TestMultiDefinition(StdoutTestCase):
    def setUp(self):
        super().setUp()
        data = yaml_safe_load(Factory().create_device("bbb-01.jinja2")[0])
        self.device = NewDevice(data)
        bbb_yaml = os.path.join(os.path.dirname(__file__), "sample_jobs/uboot-nfs.yaml")
        with open(bbb_yaml) as sample_job_data:
            self.job_data = yaml_safe_load(sample_job_data)

    def test_multidefinition(self):
        block = [
            testblock["test"]
            for testblock in self.job_data["actions"]
            if "test" in testblock
        ][0]
        self.assertIn("definitions", block)
        block["definitions"][1] = block["definitions"][0]
        self.assertEqual(len(block["definitions"]), 2)
        self.assertEqual(block["definitions"][1], block["definitions"][0])
        parser = JobParser()
        job = parser.parse(yaml_safe_dump(self.job_data), self.device, 4212, None, "")
        self.assertIsNotNone(job)
        deploy = [
            action for action in job.pipeline.actions if action.name == "tftp-deploy"
        ][0]
        tftp = [
            action
            for action in deploy.pipeline.actions
            if action.name == "prepare-tftp-overlay"
        ][0]
        overlay = [
            action for action in tftp.pipeline.actions if action.name == "lava-overlay"
        ][0]
        testdef = [
            action
            for action in overlay.pipeline.actions
            if action.name == "test-definition"
        ][0]
        runscript = [
            action
            for action in testdef.pipeline.actions
            if action.name == "test-runscript-overlay"
        ][0]
        testdef_index = runscript.get_namespace_data(
            action="test-definition", label="test-definition", key="testdef_index"
        )
        self.assertEqual(len(block["definitions"]), len(testdef_index))
        runscript.validate()
        self.assertIsNotNone(runscript.errors)
        self.assertIn("Test definition names need to be unique.", runscript.errors)


class TestMultiUBoot(StdoutTestCase):
    def setUp(self):
        super().setUp()
        factory = UBootFactory()
        self.job = factory.create_bbb_job("sample_jobs/uboot-multiple.yaml")
        self.assertIsNotNone(self.job)

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_multi_uboot(self, which_mock):
        self.assertIsNotNone(self.job)
        self.assertIsNone(self.job.validate())
        description_ref = self.pipeline_reference("uboot-multiple.yaml", job=self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe())
