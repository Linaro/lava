# Copyright (C) 2014 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


import unittest
from unittest.mock import patch

from lava_dispatcher.action import Pipeline
from lava_dispatcher.actions.boot import (
    BootloaderCommandOverlay,
    BootloaderCommandsAction,
)
from lava_dispatcher.actions.boot.ipxe import BootloaderAction, BootloaderRetry
from lava_dispatcher.actions.deploy.apply_overlay import ExtractNfsRootfs
from lava_dispatcher.actions.deploy.tftp import PrepareOverlayTftp, TftpAction
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.shell import ExpectShellSession
from lava_dispatcher.utils.network import dispatcher_ip
from lava_dispatcher.utils.strings import substitute
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase
from tests.utils import DummyLogger, infrastructure_error


class TestBootloaderAction(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.factory = Factory()

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_simulated_action(self, which_mock):
        job = self.factory.create_job("x86-01", "sample_jobs/ipxe-ramdisk.yaml")
        self.assertIsNotNone(job)

        description_ref = self.pipeline_reference("ipxe.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

        self.assertIsNone(job.validate())

    def test_tftp_pipeline(self):
        job = self.factory.create_job("x86-01", "sample_jobs/ipxe-ramdisk.yaml")
        self.assertEqual(
            [action.name for action in job.pipeline.actions],
            ["tftp-deploy", "bootloader-action", "lava-test-retry", "finalize"],
        )

        tftp = job.pipeline.find_action(TftpAction)
        self.assertTrue(
            tftp.get_namespace_data(action=tftp.name, label="tftp", key="ramdisk")
        )
        self.assertIsNotNone(tftp.pipeline)
        self.assertEqual(
            [action.name for action in tftp.pipeline.actions],
            [
                "download-retry",
                "download-retry",
                "download-retry",
                "prepare-tftp-overlay",
                "lxc-create-udev-rule-action",
                "deploy-device-env",
            ],
        )
        self.assertIn(
            "ramdisk",
            [action.key for action in tftp.pipeline.actions if hasattr(action, "key")],
        )
        self.assertIn(
            "kernel",
            [action.key for action in tftp.pipeline.actions if hasattr(action, "key")],
        )

    def test_device_x86(self):
        job = self.factory.create_job("x86-02", "sample_jobs/ipxe-ramdisk.yaml")
        self.assertEqual(
            job.device["commands"]["connections"]["uart0"]["connect"],
            "telnet bumblebee 8003",
        )
        self.assertEqual(job.device["commands"].get("interrupt", " "), " ")
        methods = job.device["actions"]["boot"]["methods"]
        self.assertIn("ipxe", methods)
        self.assertEqual(
            methods["ipxe"]["parameters"].get("bootloader_prompt"), "iPXE>"
        )

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_bootloader_action(self, which_mock):
        job = self.factory.create_job("x86-01", "sample_jobs/ipxe-ramdisk.yaml")
        job.validate()
        self.assertEqual(job.pipeline.errors, [])
        self.assertIn("ipxe", job.device["actions"]["boot"]["methods"])
        params = job.device["actions"]["boot"]["methods"]["ipxe"]["parameters"]
        boot_message = params.get(
            "boot_message", job.device.get_constant("kernel-start-message")
        )
        self.assertIsNotNone(boot_message)

        commands = job.pipeline.find_action(BootloaderCommandsAction)
        self.assertEqual(commands.character_delay, 500)

        for action in job.pipeline.actions:
            action.validate()
            if isinstance(action, BootloaderAction):
                self.assertIn("method", action.parameters)
                self.assertEqual("ipxe", action.parameters["method"])
                self.assertEqual(
                    "reboot: Restarting system",
                    action.parameters.get("parameters", {}).get(
                        "shutdown-message", job.device.get_constant("shutdown-message")
                    ),
                )
            if isinstance(action, TftpAction):
                self.assertIn("ramdisk", action.parameters)
                self.assertIn("kernel", action.parameters)
                self.assertIn("to", action.parameters)
                self.assertEqual("tftp", action.parameters["to"])
            self.assertTrue(action.valid)

    def test_overlay_action(self):
        parameters = {
            "device_type": "x86",
            "job_name": "ipxe-pipeline",
            "job_timeout": "15m",
            "action_timeout": "5m",
            "priority": "medium",
            "actions": {
                "boot": {
                    "method": "ipxe",
                    "commands": "ramdisk",
                    "prompts": ["linaro-test", "root@debian:~#"],
                },
                "deploy": {"ramdisk": "initrd.gz", "kernel": "zImage"},
            },
        }
        job = self.create_simple_job(
            device_dict=self.factory.load_device_configuration_dict("x86-01"),
            job_parameters=parameters,
        )
        pipeline = Pipeline(job=job, parameters=parameters["actions"]["boot"])
        job.pipeline = pipeline
        overlay = BootloaderCommandOverlay(job)
        pipeline.add_action(overlay)
        ip_addr = dispatcher_ip(None)
        kernel = parameters["actions"]["deploy"]["kernel"]
        ramdisk = parameters["actions"]["deploy"]["ramdisk"]

        overlay.validate()
        self.assertEqual(overlay.method, "ipxe")
        self.assertEqual(
            overlay.commands,
            [
                "dhcp net0",
                "set console console=ttyS0,115200n8 lava_mac={LAVA_MAC}",
                "set extraargs  ip=dhcp",
                "kernel tftp://{SERVER_IP}/{KERNEL} ${extraargs} ${console}",
                "initrd tftp://{SERVER_IP}/{RAMDISK}",
                "boot",
            ],
        )
        self.assertIs(overlay.use_bootscript, False)
        self.assertEqual(overlay.lava_mac, "00:90:05:af:00:7d")

        substitution_dictionary = {
            "{SERVER_IP}": ip_addr,
            "{RAMDISK}": ramdisk,
            "{KERNEL}": kernel,
            "{LAVA_MAC}": overlay.lava_mac,
        }
        params = job.device["actions"]["boot"]["methods"]
        params["ipxe"]["ramdisk"]["commands"] = substitute(
            params["ipxe"]["ramdisk"]["commands"], substitution_dictionary
        )

        commands = params["ipxe"]["ramdisk"]["commands"]
        self.assertIs(type(commands), list)
        self.assertIn("dhcp net0", commands)
        self.assertIn(
            "set console console=ttyS0,115200n8 lava_mac=00:90:05:af:00:7d", commands
        )
        self.assertIn("set extraargs  ip=dhcp", commands)
        self.assertNotIn(
            "kernel tftp://{SERVER_IP}/{KERNEL} ${extraargs} ${console}", commands
        )
        self.assertNotIn("initrd tftp://{SERVER_IP}/{RAMDISK}", commands)
        self.assertIn("boot", commands)

    def test_nbd_boot(self):
        job = self.factory.create_job("x86-01", "sample_jobs/up2-initrd-nbd.yaml")
        with patch("lava_dispatcher.actions.deploy.nbd.which") as which_mock:
            job.validate()

        which_mock.assert_any_call("nbd-server")
        which_mock.assert_any_call("in.tftpd")

        self.assertEqual(job.pipeline.errors, [])
        description_ref = self.pipeline_reference("up2-initrd-nbd.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
        self.assertIn("ipxe", job.device["actions"]["boot"]["methods"])
        for action in job.pipeline.actions:
            if isinstance(action, BootloaderAction):
                self.assertIn("method", action.parameters)
                self.assertEqual("ipxe", action.parameters["method"])
            elif isinstance(action, TftpAction):
                self.assertIn("initrd", action.parameters)
                self.assertIn("kernel", action.parameters)
                self.assertIn("nbdroot", action.parameters)
                self.assertIn("to", action.parameters)
                self.assertEqual("nbd", action.parameters["to"])
            self.assertTrue(action.valid)

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_download_action(self, which_mock):
        job = self.factory.create_job("x86-01", "sample_jobs/ipxe.yaml")
        for action in job.pipeline.actions:
            action.validate()
            self.assertTrue(action.valid)
        job.validate()
        self.assertEqual(job.pipeline.errors, [])

        overlay = job.pipeline.find_action(PrepareOverlayTftp)
        extract = overlay.pipeline.find_action(ExtractNfsRootfs)

        test_dir = overlay.get_namespace_data(
            action="test", label="results", key="lava_test_results_dir"
        )
        self.assertIsNotNone(test_dir)
        self.assertIn("/lava-", test_dir)
        self.assertIsNotNone(extract)
        self.assertEqual(extract.timeout.duration, 120)

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_reset_actions(self, which_mock):
        job = self.factory.create_job("x86-01", "sample_jobs/ipxe.yaml")
        bootloader_retry = None
        reset_action = None
        for action in job.pipeline.actions:
            action.validate()
            self.assertTrue(action.valid)

        bootloader_action = job.pipeline.find_action(BootloaderAction)
        names = [r_action.name for r_action in bootloader_action.pipeline.actions]
        self.assertIn("connect-device", names)
        self.assertIn("bootloader-retry", names)

        bootloader_retry = bootloader_action.pipeline.find_action(BootloaderRetry)
        names = [r_action.name for r_action in bootloader_retry.pipeline.actions]
        self.assertIn("reset-device", names)
        self.assertIn("bootloader-interrupt", names)
        self.assertIn("expect-shell-connection", names)
        self.assertIn("bootloader-commands", names)

        reset_action = bootloader_action.pipeline.find_action(ResetDevice)
        names = [r_action.name for r_action in reset_action.pipeline.actions]
        self.assertIn("pdu-reboot", names)

    @unittest.skipIf(infrastructure_error("telnet"), "telnet not installed")
    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_prompt_from_job(self, which_mock):
        """
        Support setting the prompt after login via the job

        Loads a known YAML, adds a prompt to the dict and re-parses the job.
        Checks that the prompt is available in the expect_shell_connection action.
        """
        job = self.factory.create_job("x86-01", "sample_jobs/ipxe-ramdisk.yaml")
        job.validate()
        job.pipeline.find_action(ExpectShellSession)

        job = self.factory.create_job("x86-01", "sample_jobs/ipxe.yaml")
        job.logger = DummyLogger()
        job.validate()
        job.pipeline.find_action(ExpectShellSession)

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_ipxe_with_monitor(self, which_mock):
        job = self.factory.create_job("x86-01", "sample_jobs/ipxe-monitor.yaml")
        job.validate()
        description_ref = self.pipeline_reference("ipxe-monitor.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
