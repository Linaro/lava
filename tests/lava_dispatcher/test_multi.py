# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from typing import Any
from unittest.mock import patch

from lava_common.decorators import nottest
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.deploy.testdef import TestRunnerAction
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase
from tests.lava_dispatcher.test_uboot import UBootFactory


class TestMultiDeploy(LavaDispatcherTestCase):
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

    @nottest
    class TestDeploy:  # cannot be a subclass of Deployment without a full select function.
        def __init__(self, parent, parameters, job):
            super().__init__()
            self.action = TestMultiDeploy.TestDeployAction(job)
            self.action.section = "internal"
            parent.add_action(self.action, parameters)

    class TestDeployAction(Action):
        name = "fake-deploy"
        description = "fake for tests only"
        summary = "fake deployment"

        def run(self, connection, max_end_time):
            self.data[self.name] = self.parameters
            return connection  # no actual connection during this fake job

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_multi_deploy(self, which_mock):
        self.assertIsNotNone(self.parsed_data)
        job = self.create_simple_job(
            device_dict=Factory().load_device_configuration_dict("bbb-01"),
            job_parameters=self.parsed_data,
        )
        pipeline = Pipeline(job=job)
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


class TestMultiDefinition(LavaDispatcherTestCase):
    def test_multidefinition(self):
        def make_duplicate_test_names(job_dict: dict[str, Any]) -> None:
            for definition_dict in job_dict["actions"][-1]["test"]["definitions"]:
                definition_dict["name"] = "smoke-tests"

        job = Factory().create_job(
            "bbb-01",
            "sample_jobs/uboot-nfs.yaml",
            job_dict_preprocessor=make_duplicate_test_names,
        )

        runscript = job.pipeline.find_action(TestRunnerAction)
        runscript.get_namespace_data(
            action="test-definition", label="test-definition", key="testdef_index"
        )
        runscript.validate()
        self.assertIsNotNone(runscript.errors)
        self.assertIn("Test definition names need to be unique.", runscript.errors)


class TestMultiUBoot(LavaDispatcherTestCase):
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
