# Copyright (C) 2014 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


import os
import unittest
from unittest.mock import patch

from lava_common.yaml import yaml_safe_dump, yaml_safe_load
from lava_dispatcher.action import Pipeline
from lava_dispatcher.actions.boot import BootloaderCommandOverlay
from lava_dispatcher.actions.boot.ipxe import BootloaderAction
from lava_dispatcher.actions.deploy.tftp import TftpAction
from lava_dispatcher.device import NewDevice
from lava_dispatcher.job import Job
from lava_dispatcher.parser import JobParser
from lava_dispatcher.utils.network import dispatcher_ip
from lava_dispatcher.utils.strings import substitute
from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase
from tests.utils import DummyLogger, infrastructure_error


class TestBootloaderAction(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.factory = Factory()

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_simulated_action(self, which_mock):
        job = self.factory.create_job("x86-01.jinja2", "sample_jobs/ipxe-ramdisk.yaml")
        self.assertIsNotNone(job)

        description_ref = self.pipeline_reference("ipxe.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

        self.assertIsNone(job.validate())

    def test_tftp_pipeline(self):
        job = self.factory.create_job("x86-01.jinja2", "sample_jobs/ipxe-ramdisk.yaml")
        self.assertEqual(
            [action.name for action in job.pipeline.actions],
            ["tftp-deploy", "bootloader-action", "lava-test-retry", "finalize"],
        )
        tftp = [
            action for action in job.pipeline.actions if action.name == "tftp-deploy"
        ][0]
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
        job = self.factory.create_job("x86-02.jinja2", "sample_jobs/ipxe-ramdisk.yaml")
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
        job = self.factory.create_job("x86-01.jinja2", "sample_jobs/ipxe-ramdisk.yaml")
        job.validate()
        self.assertEqual(job.pipeline.errors, [])
        self.assertIn("ipxe", job.device["actions"]["boot"]["methods"])
        params = job.device["actions"]["boot"]["methods"]["ipxe"]["parameters"]
        boot_message = params.get(
            "boot_message", job.device.get_constant("kernel-start-message")
        )
        self.assertIsNotNone(boot_message)
        bootloader_action = [
            action
            for action in job.pipeline.actions
            if action.name == "bootloader-action"
        ][0]
        bootloader_retry = [
            action
            for action in bootloader_action.pipeline.actions
            if action.name == "bootloader-retry"
        ][0]
        commands = [
            action
            for action in bootloader_retry.pipeline.actions
            if action.name == "bootloader-commands"
        ][0]
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
        (rendered, _) = self.factory.create_device("x86-01.jinja2")
        device = NewDevice(yaml_safe_load(rendered))
        job = Job(4212, parameters, None)
        job.device = device
        pipeline = Pipeline(job=job, parameters=parameters["actions"]["boot"])
        job.pipeline = pipeline
        overlay = BootloaderCommandOverlay()
        pipeline.add_action(overlay)
        ip_addr = dispatcher_ip(None)
        kernel = parameters["actions"]["deploy"]["kernel"]
        ramdisk = parameters["actions"]["deploy"]["ramdisk"]

        overlay.validate()
        assert overlay.method == "ipxe"
        assert overlay.commands == [
            "dhcp net0",
            "set console console=ttyS0,115200n8 lava_mac={LAVA_MAC}",
            "set extraargs  ip=dhcp",
            "kernel tftp://{SERVER_IP}/{KERNEL} ${extraargs} ${console}",
            "initrd tftp://{SERVER_IP}/{RAMDISK}",
            "boot",
        ]
        assert overlay.use_bootscript is False
        assert overlay.lava_mac == "00:90:05:af:00:7d"

        substitution_dictionary = {
            "{SERVER_IP}": ip_addr,
            "{RAMDISK}": ramdisk,
            "{KERNEL}": kernel,
            "{LAVA_MAC}": overlay.lava_mac,
        }
        params = device["actions"]["boot"]["methods"]
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

    @unittest.skipIf(infrastructure_error("nbd-server"), "nbd-server not installed")
    def test_nbd_boot(self):
        job = self.factory.create_job(
            "x86-01.jinja2", "sample_jobs/up2-initrd-nbd.yaml"
        )
        job.validate()
        self.assertEqual(job.pipeline.errors, [])
        description_ref = self.pipeline_reference("up2-initrd-nbd.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
        # Fixme: more asserts
        self.assertIn("ipxe", job.device["actions"]["boot"]["methods"])
        params = job.device["actions"]["boot"]["methods"]["ipxe"]["parameters"]
        for action in job.pipeline.actions:
            action.validate()
            if isinstance(action, BootloaderAction):
                self.assertIn("method", action.parameters)
                self.assertEqual("ipxe", action.parameters["method"])
            if isinstance(action, TftpAction):
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
        job = self.factory.create_job("x86-01.jinja2", "sample_jobs/ipxe.yaml")
        for action in job.pipeline.actions:
            action.validate()
            self.assertTrue(action.valid)
        job.validate()
        self.assertEqual(job.pipeline.errors, [])
        deploy = None
        overlay = None
        extract = None
        for action in job.pipeline.actions:
            if action.name == "tftp-deploy":
                deploy = action
        if deploy:
            for action in deploy.pipeline.actions:
                if action.name == "prepare-tftp-overlay":
                    overlay = action
        if overlay:
            for action in overlay.pipeline.actions:
                if action.name == "extract-nfsrootfs":
                    extract = action
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
        job = self.factory.create_job("x86-01.jinja2", "sample_jobs/ipxe.yaml")
        bootloader_action = None
        bootloader_retry = None
        reset_action = None
        for action in job.pipeline.actions:
            action.validate()
            self.assertTrue(action.valid)
            if action.name == "bootloader-action":
                bootloader_action = action
        names = [r_action.name for r_action in bootloader_action.pipeline.actions]
        self.assertIn("connect-device", names)
        self.assertIn("bootloader-retry", names)
        for action in bootloader_action.pipeline.actions:
            if action.name == "bootloader-retry":
                bootloader_retry = action
        names = [r_action.name for r_action in bootloader_retry.pipeline.actions]
        self.assertIn("reset-device", names)
        self.assertIn("bootloader-interrupt", names)
        self.assertIn("expect-shell-connection", names)
        self.assertIn("bootloader-commands", names)
        for action in bootloader_retry.pipeline.actions:
            if action.name == "reset-device":
                reset_action = action
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
        job = self.factory.create_job("x86-01.jinja2", "sample_jobs/ipxe-ramdisk.yaml")
        job.validate()
        bootloader = [
            action
            for action in job.pipeline.actions
            if action.name == "bootloader-action"
        ][0]
        retry = [
            action
            for action in bootloader.pipeline.actions
            if action.name == "bootloader-retry"
        ][0]
        expect = [
            action
            for action in retry.pipeline.actions
            if action.name == "expect-shell-connection"
        ][0]
        check = expect.parameters
        (rendered, _) = self.factory.create_device("x86-01.jinja2")
        device = NewDevice(yaml_safe_load(rendered))
        extra_yaml = os.path.join(os.path.dirname(__file__), "sample_jobs/ipxe.yaml")
        with open(extra_yaml) as data:
            sample_job_string = data.read()
        parser = JobParser()
        sample_job_data = yaml_safe_load(sample_job_string)
        boot = [item["boot"] for item in sample_job_data["actions"] if "boot" in item][
            0
        ]
        self.assertIsNotNone(boot)
        sample_job_string = yaml_safe_dump(sample_job_data)
        job = parser.parse(sample_job_string, device, 4212, None, "")
        job.logger = DummyLogger()
        job.validate()
        bootloader = [
            action
            for action in job.pipeline.actions
            if action.name == "bootloader-action"
        ][0]
        retry = [
            action
            for action in bootloader.pipeline.actions
            if action.name == "bootloader-retry"
        ][0]
        expect = [
            action
            for action in retry.pipeline.actions
            if action.name == "expect-shell-connection"
        ][0]

    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_ipxe_with_monitor(self, which_mock):
        job = self.factory.create_job("x86-01.jinja2", "sample_jobs/ipxe-monitor.yaml")
        job.validate()
        description_ref = self.pipeline_reference("ipxe-monitor.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())
