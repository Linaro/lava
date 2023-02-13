# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import unittest
from unittest.mock import patch

from lava_common.exceptions import ConfigurationError, JobError
from lava_common.yaml import yaml_safe_load
from lava_dispatcher.action import Action
from lava_dispatcher.actions.boot.u_boot import BootloaderInterruptAction, UBootAction
from lava_dispatcher.device import NewDevice
from lava_dispatcher.parser import JobParser
from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase
from tests.utils import DummyLogger, infrastructure_error

# Test the loading of test definitions within the deploy stage


class TestDeviceParser(StdoutTestCase):
    def test_new_device(self):
        factory = Factory()
        (rendered, _) = factory.create_device("kvm01.jinja2")
        kvm01 = yaml_safe_load(rendered)
        try:
            self.assertIsNotNone(kvm01["actions"])
        except Exception:
            self.fail("missing actions block for device")
        try:
            self.assertIsNotNone(kvm01["actions"]["boot"])
        except Exception:
            self.fail("missing boot block for device")
        try:
            self.assertIsNotNone(kvm01["actions"]["deploy"])
        except Exception:
            self.fail("missing boot block for device")
        self.assertTrue("qemu" in kvm01["actions"]["boot"]["methods"])
        self.assertTrue("image" in kvm01["actions"]["deploy"]["methods"])


class FakeAction(Action):
    name = "fake"
    description = "fake action for unit tests"
    summary = "fake action"


class TestJobDeviceParameters(StdoutTestCase):
    """
    Test parsing of device configuration into job parameters
    """

    def test_device_parser(self):
        job_parser = JobParser()
        factory = Factory()
        job = factory.create_job("bbb-01.jinja2", "sample_jobs/uboot-ramdisk.yaml")
        uboot_action = None
        device = job.device

        action = job.pipeline.actions[0]
        self.assertIn("ramdisk", action.parameters)

        action = job.pipeline.actions[1]
        self.assertIn("method", action.parameters)
        self.assertEqual("u-boot", action.parameters["method"])

        methods = device["actions"]["boot"]["methods"]
        self.assertIn("ramdisk", methods["u-boot"])
        self.assertIn("bootloader_prompt", methods["u-boot"]["parameters"])
        self.assertIsNotNone(
            methods[action.parameters["method"]][action.parameters["commands"]][
                "commands"
            ]
        )
        for line in methods[action.parameters["method"]][action.parameters["commands"]][
            "commands"
        ]:
            self.assertIsNotNone(line)
        self.assertIsInstance(action, UBootAction)
        uboot_action = action

        self.assertIsNotNone(uboot_action)
        uboot_action.validate()
        self.assertTrue(uboot_action.valid)
        for action in uboot_action.pipeline.actions:
            if isinstance(action, BootloaderInterruptAction):
                self.assertIn("power-on", action.job.device["commands"])
                self.assertIn("hard_reset", action.job.device["commands"])
                self.assertIn("connect", action.job.device["commands"])
                self.assertEqual(
                    action.job.device["commands"]["connect"].split(" ")[0], "telnet"
                )
                self.assertTrue(action.interrupt_newline)
            if isinstance(action, UBootAction):
                self.assertIn("method", action.parameters)
                self.assertIn("commands", action.parameters)
                self.assertIn("ramdisk", action.parameters["u-boot"])
                self.assertIn(
                    action.parameters["commands"],
                    action.parameters[action.parameters["method"]],
                )
                self.assertIn(
                    "commands",
                    action.parameters[action.parameters["method"]][
                        action.parameters["commands"]
                    ],
                )
                self.assertIsNotNone(action.parameters["u-boot"]["ramdisk"])
                self.assertIsInstance(
                    action.parameters["u-boot"]["ramdisk"]["commands"], list
                )
                self.assertTrue(
                    len(action.parameters["u-boot"]["ramdisk"]["commands"]) > 2
                )

    def test_device_power(self):
        factory = Factory()
        (rendered, _) = factory.create_device("bbb-01.jinja2")
        device = yaml_safe_load(rendered)
        self.assertNotEqual(device["commands"].get("hard_reset", ""), "")
        (rendered, _) = factory.create_device("kvm01.jinja2")
        device = yaml_safe_load(rendered)
        self.assertNotIn("commands", device)

    def test_device_constants(self):
        factory = Factory()
        (rendered, _) = factory.create_device("bbb-01.jinja2")
        device = NewDevice(yaml_safe_load(rendered))
        self.assertIn("constants", device)
        self.assertEqual(
            device.get_constant("kernel-start-message"), "Linux version [0-9]"
        )
        self.assertRaises(
            ConfigurationError, device.get_constant, ("non-existing-const")
        )


class TestDeviceEnvironment(StdoutTestCase):
    """
    Test parsing of device environment support
    """

    def test_empty_device_environment(self):
        factory = Factory()
        data = None
        job_parser = JobParser()
        (rendered, _) = factory.create_device("bbb-01.jinja2")
        device = NewDevice(yaml_safe_load(rendered))
        sample_job_file = os.path.join(
            os.path.dirname(__file__), "sample_jobs/uboot-ramdisk.yaml"
        )
        with open(sample_job_file) as sample_job_data:
            job = job_parser.parse(
                sample_job_data, device, 4212, None, "", env_dut=data
            )
        self.assertEqual(job.parameters["env_dut"], None)

    @unittest.skipIf(infrastructure_error("mkimage"), "u-boot-tools not installed")
    def test_device_environment_validity(self):
        """
        Use non-YAML syntax a bit like existing device config syntax.
        Ensure this syntax is picked up as invalid.
        """
        data = """
# YAML syntax.
overrides:
 DEBEMAIL = "codehelp@debian.org"
 DEBFULLNAME: "Neil Williams"
        """
        factory = Factory()
        job_parser = JobParser()
        (rendered, _) = factory.create_device("bbb-01.jinja2")
        device = NewDevice(yaml_safe_load(rendered))
        sample_job_file = os.path.join(
            os.path.dirname(__file__), "sample_jobs/uboot-ramdisk.yaml"
        )
        with open(sample_job_file) as sample_job_data:
            job = job_parser.parse(
                sample_job_data, device, 4212, None, "", env_dut=data
            )
        job.logger = DummyLogger()
        self.assertEqual(job.parameters["env_dut"], data)
        with self.assertRaises(JobError):
            job.validate()

    @unittest.skipIf(infrastructure_error("mkimage"), "u-boot-tools not installed")
    @patch(
        "lava_dispatcher.actions.deploy.tftp.which", return_value="/usr/bin/in.tftpd"
    )
    def test_device_environment(self, which_mock):
        data = """
# YAML syntax.
overrides:
 DEBEMAIL: "codehelp@debian.org"
 DEBFULLNAME: "Neil Williams"
        """
        factory = Factory()
        job_parser = JobParser()
        (rendered, _) = factory.create_device("bbb-01.jinja2")
        device = NewDevice(yaml_safe_load(rendered))
        sample_job_file = os.path.join(
            os.path.dirname(__file__), "sample_jobs/uboot-ramdisk.yaml"
        )
        with open(sample_job_file) as sample_job_data:
            job = job_parser.parse(
                sample_job_data, device, 4212, None, "", env_dut=data
            )
        job.logger = DummyLogger()
        self.assertEqual(job.parameters["env_dut"], data)
        job.validate()
        boot_actions = [
            action.pipeline.actions
            for action in job.pipeline.actions
            if action.name == "uboot-action"
        ][0]
        retry = [action for action in boot_actions if action.name == "uboot-commands"][
            0
        ]
        boot_env = [
            action
            for action in retry.pipeline.actions
            if action.name == "export-device-env"
        ][0]
        found = False
        for line in boot_env.env:
            if "DEBFULLNAME" in line:
                found = True
                # assert that the string containing a space still contains that space and is quoted
                self.assertIn("\\'Neil Williams\\'", line)
        self.assertTrue(found)


class TestCommand(StdoutTestCase):
    def test_silent(self):
        fake = FakeAction()
        command = "true"
        with self.assertWarns(DeprecationWarning):
            log = fake.run_command(command.split(" "))
        self.assertEqual(log, "")
        self.assertEqual([], fake.errors)

    def test_allow_silent(self):
        fake = FakeAction()
        command = "true"
        with self.assertWarns(DeprecationWarning):
            log = fake.run_command(command.split(" "), allow_silent=True)
        if not log:
            self.fail(log)
        self.assertEqual([], fake.errors)

    def test_error(self):
        fake = FakeAction()
        command = "false"
        # sets return code non-zero with no output
        with self.assertWarns(DeprecationWarning):
            log = fake.run_command(command.split(" "))
        self.assertFalse(log)
        self.assertNotEqual([], fake.errors)

    def test_allow_silent_error(self):
        fake = FakeAction()
        command = "false"
        with self.assertWarns(DeprecationWarning):
            log = fake.run_command(command.split(" "), allow_silent=True)
        self.assertFalse(log)
        self.assertNotEqual([], fake.errors)

    def test_invalid(self):
        fake = FakeAction()
        command = "/bin/false"
        with self.assertWarns(DeprecationWarning):
            log = fake.run_command(command.split(" "))
        self.assertFalse(log)
        self.assertNotEqual([], fake.errors)

    def test_allow_silent_invalid(self):
        fake = FakeAction()
        command = "/bin/false"
        with self.assertWarns(DeprecationWarning):
            log = fake.run_command(command.split(" "), allow_silent=True)
        self.assertFalse(log)
        self.assertNotEqual([], fake.errors)
