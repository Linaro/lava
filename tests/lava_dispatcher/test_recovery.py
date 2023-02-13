# Copyright (C) 2018-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


import os
import unittest

from lava_common.yaml import yaml_safe_load
from lava_dispatcher.device import NewDevice
from lava_dispatcher.parser import JobParser
from lava_dispatcher.utils.udev import allow_fs_label
from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase
from tests.utils import DummyLogger, infrastructure_error_multi_paths


class FastBootFactory(Factory):
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    def create_hikey_bl_device(self, hostname):
        """
        Create a device configuration on-the-fly from in-tree
        device-type Jinja2 template.
        """
        with open(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "tests",
                "lava_scheduler_app",
                "devices",
                "hi6220-hikey-bl-01.jinja2",
            )
        ) as hikey:
            data = hikey.read()
        test_template = self.prepare_jinja_template(hostname, data)
        rendered = test_template.render()
        return (rendered, data)

    def create_hikey_bl_job(self, filename):
        (data, device_dict) = self.create_hikey_bl_device("hi6220-hikey-01")
        device = NewDevice(yaml_safe_load(data))
        self.validate_data("hi6220-hikey-01", device_dict)
        fastboot_yaml = os.path.join(os.path.dirname(__file__), filename)
        with open(fastboot_yaml) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, device, 4212, None, "")
            job.logger = DummyLogger()
        return job


class UBootFactory(Factory):
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    def create_x15_bl_device(self, hostname):
        """
        Create a device configuration on-the-fly from in-tree
        device-type Jinja2 template.
        """
        with open(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "tests",
                "lava_scheduler_app",
                "devices",
                "x15-bl-01.jinja2",
            )
        ) as x15:
            data = x15.read()
        test_template = self.prepare_jinja_template(hostname, data)
        rendered = test_template.render()
        return (rendered, data)

    def create_x15_bl_job(self, filename):
        (data, device_dict) = self.create_x15_bl_device("x15-bl-01")
        device = NewDevice(yaml_safe_load(data))
        self.validate_data("x15-bl-01", device_dict)
        uboot_yaml = os.path.join(os.path.dirname(__file__), filename)
        with open(uboot_yaml) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, device, 4213, None, "")
            job.logger = DummyLogger()
        return job


class TestRecoveryMode(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.fastboot_factory = FastBootFactory()
        self.uboot_factory = UBootFactory()
        self.fastboot_job = self.fastboot_factory.create_hikey_bl_job(
            "sample_jobs/hi6220-recovery.yaml"
        )
        self.uboot_job = self.uboot_factory.create_x15_bl_job(
            "sample_jobs/x15-recovery.yaml"
        )

    @unittest.skipIf(
        infrastructure_error_multi_paths(["lxc-info", "img2simg", "simg2img"]),
        "lxc or img2simg or simg2img not installed",
    )
    def test_structure_fastboot(self):
        self.assertIsNotNone(self.fastboot_job)
        self.fastboot_job.validate()

        description_ref = self.pipeline_reference(
            "hi6220-recovery.yaml", job=self.fastboot_job
        )
        self.assertEqual(description_ref, self.fastboot_job.pipeline.describe())

        requires_board_id = not allow_fs_label(self.fastboot_job.device)
        self.assertFalse(requires_board_id)
        if "device_info" in self.fastboot_job.device:
            for usb_device in self.fastboot_job.device["device_info"]:
                if (
                    usb_device.get("board_id", "") in ["", "0000000000"]
                    and requires_board_id
                ):
                    self.fail("[LXC_CREATE] board_id unset")

    @unittest.skipIf(
        infrastructure_error_multi_paths(["lxc-info", "img2simg", "simg2img"]),
        "lxc or img2simg or simg2img not installed",
    )
    def test_structure_uboot(self):
        self.assertIsNotNone(self.uboot_job)
        self.uboot_job.validate()

        description_ref = self.pipeline_reference(
            "x15-recovery.yaml", job=self.uboot_job
        )
        self.assertEqual(description_ref, self.uboot_job.pipeline.describe())

        requires_board_id = not allow_fs_label(self.uboot_job.device)
        self.assertFalse(requires_board_id)
        if "device_info" in self.uboot_job.device:
            for usb_device in self.uboot_job.device["device_info"]:
                if (
                    usb_device.get("board_id", "") in ["", "1900d00f3b1400a2"]
                    and requires_board_id
                ):
                    self.fail("[LXC_CREATE] board_id unset")

    def test_fastboot_commands(self):
        enter = [
            action
            for action in self.fastboot_job.pipeline.actions
            if action.name == "recovery-boot"
        ][0]
        mode = [
            action
            for action in enter.pipeline.actions
            if action.name == "switch-recovery"
        ][0]
        recovery = self.fastboot_job.device["actions"]["deploy"]["methods"]["recovery"]
        self.assertIsNotNone(recovery["commands"].get(mode.mode))
        self.assertEqual(
            [
                "/home/neil/lava-lab/shared/lab-scripts/eth008_control -a 10.15.0.171 -r 1 -s off",
                "/home/neil/lava-lab/shared/lab-scripts/eth008_control -a 10.15.0.171 -r 2 -s on",
            ],
            recovery["commands"][mode.mode],
        )
        self.assertEqual("recovery_mode", mode.mode)
        exit_mode = [
            action
            for action in self.fastboot_job.pipeline.actions
            if action.name == "recovery-boot"
        ][1]
        mode = [
            action
            for action in exit_mode.pipeline.actions
            if action.name == "switch-recovery"
        ][0]
        self.assertIsNotNone(recovery["commands"].get(mode.mode))
        self.assertEqual(
            [
                "/home/neil/lava-lab/shared/lab-scripts/eth008_control -a 10.15.0.171 -r 1 -s on",
                "/home/neil/lava-lab/shared/lab-scripts/eth008_control -a 10.15.0.171 -r 2 -s off",
            ],
            recovery["commands"][mode.mode],
        )
        self.assertEqual("recovery_exit", mode.mode)

    def test_uboot_commands(self):
        enter = [
            action
            for action in self.uboot_job.pipeline.actions
            if action.name == "recovery-boot"
        ][0]
        mode = [
            action
            for action in enter.pipeline.actions
            if action.name == "switch-recovery"
        ][0]
        recovery = self.uboot_job.device["actions"]["deploy"]["methods"]["recovery"]
        self.assertIsNotNone(recovery["commands"].get(mode.mode))
        self.assertEqual(
            [
                "/usr/local/lab-scripts/eth008_control -a 192.168.0.32 -r 1 -s off",
                "/usr/local/lab-scripts/eth008_control -a 192.168.0.32 -r 2 -s off",
                "/usr/local/lab-scripts/eth008_control -a 192.168.0.32 -r 3 -s off",
                "/usr/local/lab-scripts/eth008_control -a 192.168.0.32 -r 4 -s off",
            ],
            recovery["commands"][mode.mode],
        )
        self.assertEqual("recovery_mode", mode.mode)
        exit_mode = [
            action
            for action in self.fastboot_job.pipeline.actions
            if action.name == "recovery-boot"
        ][1]
        mode = [
            action
            for action in exit_mode.pipeline.actions
            if action.name == "switch-recovery"
        ][0]
        self.assertIsNotNone(recovery["commands"].get(mode.mode))
        self.assertEqual(
            [
                "/usr/local/lab-scripts/eth008_control -a 192.168.0.32 -r 1 -s on",
                "/usr/local/lab-scripts/eth008_control -a 192.168.0.32 -r 2 -s on",
                "/usr/local/lab-scripts/eth008_control -a 192.168.0.32 -r 3 -s on",
                "/usr/local/lab-scripts/eth008_control -a 192.168.0.32 -r 4 -s on",
            ],
            recovery["commands"][mode.mode],
        )
        self.assertEqual("recovery_exit", mode.mode)
