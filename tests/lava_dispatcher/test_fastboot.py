# Copyright (C) 2015 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import glob
import os
import unittest
from unittest.mock import ANY, MagicMock, PropertyMock, patch

from lava_common.exceptions import InfrastructureError, JobError
from lava_dispatcher.actions.deploy.fastboot import FastbootFlashOrderAction
from lava_dispatcher.protocols.lxc import LxcProtocol
from lava_dispatcher.utils.adb import OptionalContainerAdbAction
from lava_dispatcher.utils.containers import DockerDriver, LxcDriver, NullDriver
from lava_dispatcher.utils.fastboot import OptionalContainerFastbootAction
from lava_dispatcher.utils.lxc import is_lxc_requested, lxc_cmd_prefix
from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase
from tests.utils import infrastructure_error, infrastructure_error_multi_paths


class FastBootFactory(Factory):
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    def create_fastboot_job(self, filename):
        return self.create_job("nexus4-01.jinja2", filename)

    def create_db410c_job(self, filename):
        return self.create_job("db410c-01.jinja2", filename)

    def create_x15_job(self, filename):
        return self.create_job("x15-01.jinja2", filename)

    def create_hikey_job(self, filename):
        return self.create_job("hi6220-hikey-r2-01.jinja2", filename)

    def create_hikey960_job(self, filename):
        return self.create_job("hi960-hikey-01.jinja2", filename)

    def create_nexus5x_job(self, filename):
        return self.create_job("nexus5x-01.jinja2", filename)

    def create_pixel_job(self, filename):
        return self.create_job("pixel-01.jinja2", filename)


class TestFastbootBaseAction(unittest.TestCase):
    def setUp(self):
        self.factory = FastBootFactory()

    def test_null_driver(self):
        job = self.factory.create_fastboot_job("sample_jobs/nexus4-minus-lxc.yaml")
        action = job.pipeline.actions[0]
        self.assertIsInstance(action.driver, NullDriver)

    def test_lxc_driver(self):
        job = self.factory.create_fastboot_job("sample_jobs/fastboot.yaml")
        action = job.pipeline.actions[2]
        self.assertIsInstance(action.driver, LxcDriver)

    def test_docker_driver(self):
        job = self.factory.create_fastboot_job("sample_jobs/fastboot-docker.yaml")
        action = job.pipeline.actions[0]
        self.assertIsInstance(action.driver, DockerDriver)


class TestFastbootBaseActionDriverUsage(unittest.TestCase):
    def setUp(self):
        class OptionalContainerAndroidAction(
            OptionalContainerFastbootAction, OptionalContainerAdbAction
        ):
            pass

        action = OptionalContainerAndroidAction()
        action.job = MagicMock()
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


class TestNullDriver(unittest.TestCase):
    def setUp(self):
        self.factory = FastBootFactory()
        job = self.factory.create_fastboot_job("sample_jobs/nexus4-minus-lxc.yaml")
        self.action = job.pipeline.actions[0]

    @patch(
        "lava_dispatcher.actions.deploy.fastboot.OptionalContainerFastbootAction.run_cmd"
    )
    def test_run_fastboot(self, run_cmd):
        self.action.run_fastboot(["wait-for-devices"])
        run_cmd.assert_called_with(["fastboot", "-s", ANY, "wait-for-devices"])

    def test_maybe_copy_to_container(self):
        src = "/path/to/file.img"
        self.assertEqual(src, self.action.maybe_copy_to_container(src))


class TestLxcDriver(unittest.TestCase):
    def setUp(self):
        self.factory = FastBootFactory()
        job = self.factory.create_fastboot_job("sample_jobs/fastboot.yaml")
        self.action = job.pipeline.actions[2]
        self.lxc_name = "lxc-nexus4-test-" + str(self.action.job.job_id)

    @patch(
        "lava_dispatcher.actions.deploy.fastboot.OptionalContainerFastbootAction.run_cmd"
    )
    def test_run_fastboot(self, run_cmd):
        self.action.run_fastboot(["wait-for-devices"])
        run_cmd.assert_called_with(
            [
                "lxc-attach",
                "-n",
                self.lxc_name,
                "--",
                "fastboot",
                "-s",
                ANY,
                "wait-for-devices",
            ]
        )

    @patch(
        "lava_dispatcher.utils.containers.copy_to_lxc",
        return_value="/path/inside/container/to/file.img",
    )
    def test_maybe_copy_to_container(self, copy_to_lxc):
        src = "/path/to/file.img"
        dest = self.action.maybe_copy_to_container(src)
        copy_to_lxc.assert_called_with(self.lxc_name, src, ANY)
        self.assertEqual(dest, "/path/inside/container/to/file.img")


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

    @patch("lava_dispatcher_host.get_mapping_path")
    @patch("lava_dispatcher.action.Action.run_cmd")
    @patch("subprocess.check_call")
    @patch(
        "lava_dispatcher.utils.containers.get_udev_devices",
        return_value=["/dev/foo/bar"],
    )
    def test_run_fastboot(
        self, get_udev_devices, check_call, run_cmd, get_mapping_path
    ):
        get_mapping_path.return_value = "/tmp/usbmap.yaml"  # FIXME
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


class TestFastbootDeploy(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.factory = FastBootFactory()
        self.job = self.factory.create_fastboot_job("sample_jobs/fastboot.yaml")

    def test_deploy_job(self):
        self.assertEqual(self.job.pipeline.job, self.job)
        self.assertIsInstance(self.job.device["device_info"], list)
        for action in self.job.pipeline.actions:
            self.assertEqual(action.job, self.job)

    def test_pipeline(self):
        description_ref = self.pipeline_reference("fastboot.yaml", job=self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe())

    @unittest.skipIf(
        infrastructure_error_multi_paths(["lxc-info", "img2simg", "simg2img"]),
        "lxc or img2simg or simg2img not installed",
    )
    def test_lxc_api(self):
        job = self.factory.create_hikey_job("sample_jobs/hikey-oe.yaml")
        description_ref = self.pipeline_reference("hikey-oe.yaml", job=job)
        job.validate()
        self.assertEqual(description_ref, job.pipeline.describe())
        self.assertIn(LxcProtocol.name, [protocol.name for protocol in job.protocols])
        self.assertEqual(len(job.protocols), 1)
        self.assertIsNotNone(job.device.pre_os_command)
        select = [
            action
            for action in job.pipeline.actions
            if action.name == "grub-sequence-action"
        ][0]
        self.assertIn(LxcProtocol.name, select.parameters.keys())
        self.assertIn("protocols", select.parameters.keys())
        self.assertIn(LxcProtocol.name, select.parameters["protocols"].keys())
        self.assertEqual(len(select.parameters["protocols"][LxcProtocol.name]), 1)
        lxc_active = any(
            [
                protocol
                for protocol in job.protocols
                if protocol.name == LxcProtocol.name
            ]
        )
        self.assertTrue(lxc_active)
        for calling in select.parameters["protocols"][LxcProtocol.name]:
            self.assertEqual(calling["action"], select.name)
            self.assertEqual(calling["request"], "pre-os-command")
        deploy = [
            action
            for action in job.pipeline.actions
            if action.name == "fastboot-deploy"
        ][0]
        self.assertIn(LxcProtocol.name, deploy.parameters.keys())
        self.assertIn("protocols", deploy.parameters.keys())
        self.assertIn(LxcProtocol.name, deploy.parameters["protocols"].keys())
        self.assertEqual(len(deploy.parameters["protocols"][LxcProtocol.name]), 1)
        for calling in deploy.parameters["protocols"][LxcProtocol.name]:
            self.assertEqual(calling["action"], deploy.name)
            self.assertEqual(calling["request"], "pre-power-command")
        pair = ["pre-os-command", "pre-power-command"]
        action_list = {list(jaction.keys())[0] for jaction in job.parameters["actions"]}
        block = job.parameters["actions"]
        for action in action_list:
            for item in block:
                if action in item:
                    if "protocols" in item[action]:
                        caller = item[action]["protocols"][LxcProtocol.name]
                        for call in caller:
                            self.assertIn(call["request"], pair)

    @unittest.skipIf(infrastructure_error("lxc-info"), "lxc-info not installed")
    def test_fastboot_lxc(self):
        job = self.factory.create_hikey_job("sample_jobs/hi6220-hikey.yaml")

        description_ref = self.pipeline_reference("hi6220-hikey.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
        self.assertEqual(
            job.device.pre_power_command,
            "/home/neil/lava-lab/shared/lab-scripts/usb_hub_control -u 12 -p 4000 -m sync",
        )
        lxc_deploy = [
            action for action in job.pipeline.actions if action.name == "lxc-deploy"
        ][0]
        overlay = [
            action
            for action in lxc_deploy.pipeline.actions
            if action.name == "lava-overlay"
        ][0]
        testdef = [
            action
            for action in overlay.pipeline.actions
            if action.name == "test-definition"
        ][0]
        job.validate()
        self.assertEqual(
            {
                "1.8.4.20": "4_android-optee",
                "1.8.4.4": "0_get-adb-serial",
                "1.8.4.12": "2_android-busybox",
                "1.8.4.8": "1_android-meminfo",
                "1.8.4.16": "3_android-ping-dns",
            },
            testdef.get_namespace_data(
                action="test-runscript-overlay",
                label="test-runscript-overlay",
                key="testdef_levels",
            ),
        )
        for testdef in testdef.test_list[0]:
            self.assertEqual("git", testdef["from"])

    @unittest.skipIf(infrastructure_error("lxc-create"), "lxc-create not installed")
    def test_validate(self):
        try:
            self.job.pipeline.validate_actions()
        except JobError as exc:
            self.fail(exc)
        for action in self.job.pipeline.actions:
            self.assertEqual([], action.errors)

    def test_overlay(self):
        overlay = None
        action = self.job.pipeline.actions[0]
        self.assertEqual(action.parameters["namespace"], "tlxc")
        overlay = [
            action
            for action in action.pipeline.actions
            if action.name == "lava-overlay"
        ][0]
        self.assertIsNotNone(overlay)
        # these tests require that lava-dispatcher itself is installed, not just running tests from a git clone
        self.assertTrue(os.path.exists(overlay.lava_test_dir))
        self.assertIsNot(overlay.lava_test_dir, "/")
        self.assertNotIn("lava_multi_node_test_dir", dir(overlay))
        self.assertNotIn("lava_multi_node_cache_file", dir(overlay))
        self.assertNotIn("lava_lmp_test_dir", dir(overlay))
        self.assertNotIn("lava_lmp_cache_file", dir(overlay))
        self.assertIsNotNone(
            overlay.parameters["deployment_data"]["lava_test_results_dir"]
        )
        self.assertIsNotNone(overlay.parameters["deployment_data"]["lava_test_sh_cmd"])
        self.assertEqual(overlay.parameters["deployment_data"]["distro"], "debian")
        self.assertIsNotNone(
            overlay.parameters["deployment_data"]["lava_test_results_part_attr"]
        )
        self.assertIsNotNone(glob.glob(os.path.join(overlay.lava_test_dir, "lava-*")))

    @unittest.skipIf(infrastructure_error("lxc-attach"), "lxc-attach not installed")
    def test_boot(self):
        action = self.job.pipeline.actions[1]
        self.assertEqual(action.parameters.get("namespace"), "tlxc")
        self.assertIn(action.parameters["method"], ["lxc", "fastboot"])
        self.assertEqual(action.parameters["prompts"], ["root@(.*):/#"])

        action = self.job.pipeline.actions[3]
        self.assertEqual(action.parameters.get("namespace"), "droid")
        self.assertIn(action.parameters["method"], ["lxc", "fastboot"])
        self.assertEqual(action.parameters.get("prompts"), None)

    def test_testdefinitions(self):
        for action in self.job.pipeline.actions:
            if action.name == "test":
                # get the action & populate it
                self.assertEqual(len(action.parameters["definitions"]), 2)

    def test_udev_actions(self):
        self.factory = FastBootFactory()
        job = self.factory.create_db410c_job("sample_jobs/db410c.yaml")
        self.assertTrue(job.device.get("fastboot_via_uboot", True))
        description_ref = self.pipeline_reference("db410c.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
        boot = [
            action for action in job.pipeline.actions if action.name == "fastboot-boot"
        ][0]

    @unittest.skipIf(infrastructure_error("lxc-start"), "lxc-start not installed")
    def test_x15_job(self):
        self.factory = FastBootFactory()
        job = self.factory.create_x15_job("sample_jobs/x15.yaml")
        job.validate()
        description_ref = self.pipeline_reference("x15.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
        deploy = [
            action
            for action in job.pipeline.actions
            if action.name == "fastboot-deploy"
        ][0]
        enter = [
            action
            for action in deploy.pipeline.actions
            if action.name == "uboot-enter-fastboot"
        ][0]
        interrupt = [
            action
            for action in enter.pipeline.actions
            if action.name == "bootloader-interrupt"
        ][0]
        self.assertTrue(interrupt.needs_interrupt)
        self.assertIsInstance(interrupt.params, dict)
        self.assertNotEqual(interrupt.params, {})
        self.assertIn("interrupt_prompt", interrupt.params)
        boot = [
            action for action in job.pipeline.actions if action.name == "fastboot-boot"
        ][0]
        enter = [
            action
            for action in boot.pipeline.actions
            if action.name == "uboot-enter-fastboot"
        ][0]
        interrupt = [
            action
            for action in enter.pipeline.actions
            if action.name == "bootloader-interrupt"
        ][0]
        self.assertIsInstance(interrupt.params, dict)
        self.assertNotEqual(interrupt.params, {})
        self.assertIn("interrupt_prompt", interrupt.params)
        self.assertTrue(interrupt.needs_interrupt)
        autologin = [
            action
            for action in boot.pipeline.actions
            if action.name == "auto-login-action"
        ][0]
        self.assertTrue(autologin.booting)
        self.assertEqual(
            set(autologin.parameters.get("prompts")),
            {"root@(.*):/#", "shell@am57xevm:/"},
        )
        self.assertIsNone(autologin.parameters.get("boot_message"))

    def test_sdm845_qcs(self):
        self.factory = FastBootFactory()
        job = self.factory.create_job(
            "qcs404-evb-1k-01.jinja2", "sample_jobs/qcs404-evb-1k.yaml"
        )
        # do not run job.validate() - power urls do not exist.
        description_ref = self.pipeline_reference("qcs404-evb-1k.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
        job = self.factory.create_job(
            "qcs404-evb-4k-01.jinja2", "sample_jobs/qcs404-evb-4k.yaml"
        )
        # do not run job.validate() - power urls do not exist.
        description_ref = self.pipeline_reference("qcs404-evb-4k.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

    def test_nexus5x_job(self):
        self.factory = FastBootFactory()
        job = self.factory.create_nexus5x_job("sample_jobs/nexus5x.yaml")
        # do not run job.validate() - urls no longer exist.
        description_ref = self.pipeline_reference("nexus5x.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

    def test_pixel_job(self):
        self.factory = FastBootFactory()
        job = self.factory.create_pixel_job("sample_jobs/pixel.yaml")
        # do not run job.validate() - urls no longer exist.
        description_ref = self.pipeline_reference("pixel.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

    def test_flash_cmds_order(self):
        self.factory = FastBootFactory()
        job = self.factory.create_db410c_job("sample_jobs/db410c.yaml")
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
        flash_order = None
        action = job.pipeline.actions[2]
        self.assertEqual(action.name, "fastboot-deploy")
        flash_order = [
            action
            for action in action.pipeline.actions
            if action.name == "fastboot-flash-order-action"
        ][0]
        flash_action = [
            action
            for action in flash_order.pipeline.actions
            if action.name == "fastboot-flash-action"
        ][0]
        flash_cmds = [
            action.command
            for action in flash_order.pipeline.actions
            if action.name == "fastboot-flash-action"
        ]
        self.assertIsNotNone(flash_order)
        self.assertIsNotNone(flash_action)
        self.assertEqual(flash_action.timeout_exception, InfrastructureError)
        self.assertIsInstance(flash_order, FastbootFlashOrderAction)
        self.assertEqual(expected_flash_cmds, flash_cmds)

    @unittest.skipIf(infrastructure_error("lxc-start"), "lxc-start not installed")
    def test_hikey960_fastboot(self):
        job = self.factory.create_hikey960_job("sample_jobs/hikey960-aosp.yaml")
        self.assertIsNotNone(job)
        job.validate()
        description_ref = self.pipeline_reference("hi960-aosp-efi.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
        flash_order = None
        expected_flash_cmds = ["boot", "system", "userdata", "cache"]
        action = job.pipeline.actions[2]
        self.assertEqual(action.name, "fastboot-deploy")
        flash_order = [
            action
            for action in action.pipeline.actions
            if action.name == "fastboot-flash-order-action"
        ][0]
        flash_cmds = [
            action.command
            for action in flash_order.pipeline.actions
            if action.name == "fastboot-flash-action"
        ]
        self.assertIsNotNone(flash_order)
        self.assertIsInstance(flash_order, FastbootFlashOrderAction)
        self.assertEqual(expected_flash_cmds, flash_cmds)

    def test_fastboot_minus_lxc(self):
        # Do not run job.validate() since it will require some android tools
        # such as fastboot, adb, etc. to be installed.
        job = self.factory.create_fastboot_job("sample_jobs/nexus4-minus-lxc.yaml")
        description_ref = self.pipeline_reference("nexus4-minus-lxc.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
        # There shouldn't be any lxc defined
        lxc_name = is_lxc_requested(job)
        self.assertEqual(lxc_name, False)
        deploy = [
            action
            for action in job.pipeline.actions
            if action.name == "fastboot-deploy"
        ][0]
        # No lxc requested, hence lxc_cmd_prefix is an empty list
        self.assertEqual([], lxc_cmd_prefix(job))

    def test_db410c_minus_lxc(self):
        # Do not run job.validate() since it will require some android tools
        # such as fastboot, adb, etc. to be installed.
        job = self.factory.create_db410c_job("sample_jobs/db410c-minus-lxc.yaml")
        description_ref = self.pipeline_reference("db410c-minus-lxc.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
        # There shouldn't be any lxc defined
        lxc_name = is_lxc_requested(job)
        self.assertEqual(lxc_name, False)
        deploy = [
            action
            for action in job.pipeline.actions
            if action.name == "fastboot-deploy"
        ][0]
        # No lxc requested, hence lxc_cmd_prefix is an empty list
        self.assertEqual([], lxc_cmd_prefix(job))

    def test_fastboot_boot_commands(self):
        job = self.factory.create_job(
            "imx8mq-evk-01.jinja2", "sample_jobs/imx8mq-evk.yaml"
        )
        boot = [
            action for action in job.pipeline.actions if action.name == "fastboot-boot"
        ][0]
        self.assertIn("commands", boot.parameters)
        self.assertEqual("191c51d6f060954b", job.device["fastboot_serial_number"])
        self.assertIsInstance(boot.parameters["commands"], list)

    def test_fastboot_plus_reboot(self):
        job = self.factory.create_job(
            "imx8mq-evk-01.jinja2", "sample_jobs/imx8mq-evk-with-flash-reboot.yaml"
        )
        description_ref = self.pipeline_reference(
            "imx8mq-evk-with-flash-reboot.yaml", job=job
        )
        self.assertEqual(description_ref, job.pipeline.describe())
