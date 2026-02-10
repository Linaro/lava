# Copyright (C) 2015 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import glob
import os
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import ANY, PropertyMock, patch

from lava_common.exceptions import FastbootDeviceNotFound, InfrastructureError, JobError
from lava_dispatcher.actions.boot import AutoLoginAction, BootloaderInterruptAction
from lava_dispatcher.actions.boot.fastboot import BootFastbootAction
from lava_dispatcher.actions.boot.grub import GrubSequenceAction
from lava_dispatcher.actions.deploy.fastboot import FastbootAction, FastbootFlashAction
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.actions.deploy.testdef import TestDefinitionAction
from lava_dispatcher.utils.adb import OptionalContainerAdbAction
from lava_dispatcher.utils.containers import DockerDriver, NullDriver
from lava_dispatcher.utils.fastboot import OptionalContainerFastbootAction
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase
from tests.utils import infrastructure_error, infrastructure_error_multi_paths


class FastBootFactory(Factory):
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    def create_fastboot_job(self, filename):
        return self.create_job("nexus4-01", filename)

    def create_db410c_job(self, filename):
        return self.create_job("db410c-01", filename)

    def create_x15_job(self, filename):
        return self.create_job("x15-01", filename)

    def create_hikey_job(self, filename):
        return self.create_job("hi6220-hikey-r2-01", filename)

    def create_hikey960_job(self, filename):
        return self.create_job("hi960-hikey-01", filename)

    def create_nexus5x_job(self, filename):
        return self.create_job("nexus5x-01", filename)

    def create_pixel_job(self, filename):
        return self.create_job("pixel-01", filename)

    def create_db410c_auto_job(self, filename):
        return self.create_job("db410c-auto-01", filename)


class TestFastbootBaseAction(unittest.TestCase):
    def setUp(self):
        self.factory = FastBootFactory()

    def test_docker_driver(self):
        job = self.factory.create_fastboot_job("sample_jobs/fastboot-docker.yaml")
        action = job.pipeline.actions[0]
        self.assertIsInstance(action.driver, DockerDriver)


class TestFastbootBaseActionDriverUsage(LavaDispatcherTestCase):
    def setUp(self):
        class OptionalContainerAndroidAction(
            OptionalContainerFastbootAction, OptionalContainerAdbAction
        ):
            pass

        job = self.create_job_mock()
        action = OptionalContainerAndroidAction(job)
        action.job.device = {
            "adb_serial_number": "01234556789",
            "fastboot_serial_number": "01234556789",
            "fastboot_options": [],
        }

        driver_patcher = patch(
            "lava_dispatcher.actions.deploy.fastboot.OptionalContainerFastbootAction.driver",
            new_callable=PropertyMock,
        )
        action.driver = driver_patcher.start()
        self.addCleanup(driver_patcher.stop)

        self.action = action

        run_maybe_in_container_patcher = patch(
            "lava_dispatcher.actions.deploy.fastboot.OptionalContainerFastbootAction.run_maybe_in_container"
        )
        self.run_maybe_in_container = run_maybe_in_container_patcher.start()
        self.addCleanup(run_maybe_in_container_patcher.stop)

        get_output_maybe_in_container_patcher = patch(
            "lava_dispatcher.actions.deploy.fastboot.OptionalContainerFastbootAction.get_output_maybe_in_container"
        )
        self.get_output_maybe_in_container = (
            get_output_maybe_in_container_patcher.start()
        )
        self.addCleanup(get_output_maybe_in_container_patcher.stop)

    def test_run_fastboot(self):
        self.action.run_fastboot(["xyz"])
        self.run_maybe_in_container.assert_called_with(
            ["fastboot", "-s", "01234556789", "xyz"]
        )

    def test_get_fastboot_output(self):
        self.get_output_maybe_in_container.return_value = "HELLO"
        output = self.action.get_fastboot_output(["devices"])
        self.assertEqual("HELLO", output)

    def test_get_fastboot_output_kwards(self):
        self.action.get_fastboot_output(["devices"], foo="bar")
        self.get_output_maybe_in_container.assert_called_with(ANY, foo="bar")

    def test_run_adb(self):
        self.action.run_adb(["devices"])
        self.run_maybe_in_container.assert_called_with(
            ["adb", "-s", "01234556789", "devices"]
        )

    def test_get_adb_output(self):
        self.get_output_maybe_in_container.return_value = "HELLO"
        output = self.action.get_adb_output(["devices"])
        self.assertEqual("HELLO", output)

    def test_get_adb_output_kwards(self):
        self.action.get_adb_output(["devices"], foo="bar")
        self.get_output_maybe_in_container.assert_called_with(ANY, foo="bar")


class TestDockerDriver(unittest.TestCase):
    def setUp(self):
        self.factory = FastBootFactory()
        job = self.factory.create_fastboot_job("sample_jobs/fastboot-docker.yaml")
        self.action = job.pipeline.actions[0]
        self.image = self.action.parameters["docker"]["image"]

    def test_maybe_copy_to_container(self):
        src = "/path/to/image.img"
        dest = self.action.maybe_copy_to_container(src)
        self.assertEqual(src, dest)

    @patch("lava_common.device_mappings.get_mapping_path")
    @patch("lava_dispatcher.action.Action.run_cmd")
    @patch("subprocess.check_call")
    @patch(
        "lava_dispatcher.utils.containers.get_udev_devices",
        return_value=["/dev/foo/bar"],
    )
    def test_run_fastboot(
        self, get_udev_devices, check_call, run_cmd, get_mapping_path
    ):
        get_mapping_path.return_value = Path("/tmp/usbmap.yaml")  # FIXME
        self.action.maybe_copy_to_container("/path/to/image.img")
        self.action.run_fastboot(["wait-for-devices"])
        cmd = run_cmd.call_args[0][0]
        assert len(run_cmd.mock_calls) == 4

        assert run_cmd.mock_calls[0].args[0][0:5] == [
            "docker",
            "run",
            "--detach",
            "--rm",
            "--init",
        ]
        assert run_cmd.mock_calls[0].args[0][6:10] == [
            "--mount=type=bind,source=/path/to/image.img,destination=/path/to/image.img",
            "some-fastboot-image",
            "sleep",
            "infinity",
        ]

        assert run_cmd.mock_calls[1].args[0] == [
            "udevadm",
            "trigger",
            "--action=add",
            "/dev/foo/bar",
        ]
        assert run_cmd.mock_calls[1].kwargs == {"allow_fail": True}
        assert run_cmd.mock_calls[2].args[0][0:2] == ["docker", "exec"]
        assert run_cmd.mock_calls[2].args[0][-4:] == [
            "fastboot",
            "-s",
            "04f228d1d9c76f39",
            "wait-for-devices",
        ]

        assert run_cmd.mock_calls[3].args[0][0:2] == ["docker", "stop"]


class TestFastbootDeploy(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.factory = FastBootFactory()
        self.job = self.factory.create_fastboot_job("sample_jobs/fastboot-docker.yaml")

    def test_deploy_job(self):
        self.assertEqual(self.job.pipeline.job, self.job)
        self.assertIsInstance(self.job.device["device_info"], list)
        for action in self.job.pipeline.actions:
            self.assertEqual(action.job, self.job)

    def test_pipeline(self):
        description_ref = self.pipeline_reference("fastboot-docker.yaml", job=self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe())

    def test_testdefinitions(self):
        for action in self.job.pipeline.actions:
            if action.name == "test":
                # get the action & populate it
                self.assertEqual(len(action.parameters["definitions"]), 2)

    def test_udev_actions(self):
        self.factory = FastBootFactory()
        job = self.factory.create_db410c_job("sample_jobs/docker-test-db410c.yaml")
        self.assertTrue(job.device.get("fastboot_via_uboot", True))
        description_ref = self.pipeline_reference("db410c.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

    def test_flash_cmds_order(self):
        self.factory = FastBootFactory()
        job = self.factory.create_db410c_job("sample_jobs/docker-test-db410c.yaml")
        # The expected_flash_cmds list ensures the following:
        # 1. Order of flash commands.
        # 2. Number / Count of flash commands.
        # 3. 'cdt' flash command is not part of draganboard-410c's device
        #    dictionary, but ensure that it gets added in the final flash
        #    commands list.
        expected_flash_cmds = [
            "partition",
            "hyp",
            "rpm",
            "sbl1",
            "tz",
            "aboot",
            "cdt",
            "boot",
            "rootfs",
        ]

        flash_actions = job.pipeline.find_all_actions(FastbootFlashAction)
        flash_cmds = [action.command for action in flash_actions]
        self.assertEqual(FastbootFlashAction.timeout_exception, InfrastructureError)
        self.assertEqual(expected_flash_cmds, flash_cmds)

    def test_fastboot_boot_commands(self):
        job = self.factory.create_job("imx8mq-evk-01", "sample_jobs/imx8mq-evk.yaml")
        boot = job.pipeline.find_action(BootFastbootAction)

        self.assertIn("commands", boot.parameters)
        self.assertEqual("191c51d6f060954b", job.device["fastboot_serial_number"])
        self.assertIsInstance(boot.parameters["commands"], list)


class TestFastbootDeployAutoDetection(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.factory = FastBootFactory()
        self.job = self.factory.create_db410c_auto_job(
            "sample_jobs/fastboot-docker.yaml"
        )

    @patch(
        "lava_dispatcher.utils.fastboot.which",
        return_value="/usr/bin/fastboot",
    )
    @patch("lava_dispatcher.utils.containers.DockerRun.prepare")
    def test_validate(self, *args):
        try:
            self.job.pipeline.validate_actions()
        except JobError as exc:
            self.fail(exc)
        for action in self.job.pipeline.actions:
            self.assertEqual([], action.errors)

    def test_deploy_job(self):
        self.assertEqual(self.job.pipeline.job, self.job)
        self.assertIsInstance(self.job.device["device_info"], list)
        self.assertIsInstance(self.job.device["device_info"][0], dict)
        self.assertEqual(
            self.job.device["device_info"][0].get("board_id"), "0000000000"
        )
        for action in self.job.pipeline.actions:
            self.assertEqual(action.job, self.job)

    def test_pipeline(self):
        description_ref = self.pipeline_reference(
            "fastboot-auto-detections.yaml", job=self.job
        )
        self.assertEqual(description_ref, self.job.pipeline.describe())

    @patch(
        "lava_dispatcher.utils.fastboot.subprocess.run",
        return_value=CompletedProcess(
            ["/usr/bin/fastboot", "devices"],
            0,
            stdout="a2c22e48\tfastboot\n",
            stderr="",
        ),
    )
    @patch("time.sleep")
    def test_fastboot_auto_detection(self, *args):
        self.assertEqual(self.job.device["fastboot_serial_number"], "0000000000")
        self.assertEqual(self.job.device["adb_serial_number"], "0000000000")
        self.assertIsNone(self.job.device.get("board_id"))
        self.assertEqual(self.job.device["device_info"], [{"board_id": "0000000000"}])

        action = self.job.pipeline.actions[0].pipeline.actions[4]
        action.run(None, None)

        self.assertEqual(self.job.device["fastboot_serial_number"], "a2c22e48")
        self.assertEqual(self.job.device["adb_serial_number"], "a2c22e48")
        self.assertEqual(self.job.device["board_id"], "a2c22e48")
        self.assertEqual(self.job.device["device_info"], [{"board_id": "a2c22e48"}])

    @patch(
        "lava_dispatcher.utils.fastboot.subprocess.run",
        return_value=CompletedProcess(
            ["/usr/bin/fastboot", "devices"],
            0,
            stdout="",
            stderr="",
        ),
    )
    @patch("time.sleep")
    def test_fastboot_auto_detection_none(self, *args):
        action = self.job.pipeline.actions[0].pipeline.actions[4]

        with self.assertRaises(FastbootDeviceNotFound) as context:
            action.run(None, None)

        self.assertEqual(
            str(context.exception),
            "Fastboot device not found.",
        )

    @patch(
        "lava_dispatcher.utils.fastboot.subprocess.run",
        return_value=CompletedProcess(
            ["/usr/bin/fastboot", "devices"],
            0,
            stdout="a2c22e48\tfastboot\n1de55d7f32c101b8\tfastboot\n",
            stderr="",
        ),
    )
    @patch("time.sleep")
    def test_fastboot_auto_detection_multiple(self, *args):
        action = self.job.pipeline.actions[0].pipeline.actions[4]

        with self.assertRaises(JobError) as context:
            action.run(None, None)

        self.assertEqual(
            str(context.exception),
            "More then one fastboot devices found: ['a2c22e48', '1de55d7f32c101b8']",
        )
