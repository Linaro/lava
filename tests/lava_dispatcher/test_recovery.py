# Copyright (C) 2018-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


import unittest

from lava_dispatcher.actions.boot.recovery import (
    RecoveryBootAction,
    SwitchRecoveryCommand,
)
from lava_dispatcher.utils.udev import allow_fs_label
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase
from tests.utils import infrastructure_error_multi_paths


class TestRecoveryMode(LavaDispatcherTestCase):
    def create_fastboot_job(self):
        return Factory().create_job(
            "hi6220-hikey-bl-01", "sample_jobs/hi6220-recovery.yaml"
        )

    def create_uboot_job(self):
        return Factory().create_job("x15-bl-01", "sample_jobs/x15-recovery.yaml")

    @unittest.skipIf(
        infrastructure_error_multi_paths(["lxc-info", "img2simg", "simg2img"]),
        "lxc or img2simg or simg2img not installed",
    )
    def test_structure_fastboot(self):
        fastboot_job = self.create_fastboot_job()
        self.assertIsNotNone(fastboot_job)
        fastboot_job.validate()

        description_ref = self.pipeline_reference(
            "hi6220-recovery.yaml", job=fastboot_job
        )
        self.assertEqual(description_ref, fastboot_job.pipeline.describe())

        requires_board_id = not allow_fs_label(fastboot_job.device)
        self.assertFalse(requires_board_id)
        if "device_info" in fastboot_job.device:
            for usb_device in fastboot_job.device["device_info"]:
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
        uboot_job = self.create_uboot_job()
        self.assertIsNotNone(uboot_job)
        uboot_job.validate()

        description_ref = self.pipeline_reference("x15-recovery.yaml", job=uboot_job)
        self.assertEqual(description_ref, uboot_job.pipeline.describe())

        requires_board_id = not allow_fs_label(uboot_job.device)
        self.assertFalse(requires_board_id)
        if "device_info" in uboot_job.device:
            for usb_device in uboot_job.device["device_info"]:
                if (
                    usb_device.get("board_id", "") in ["", "1900d00f3b1400a2"]
                    and requires_board_id
                ):
                    self.fail("[LXC_CREATE] board_id unset")

    def test_fastboot_commands(self):
        fastboot_job = self.create_fastboot_job()

        enter, exit = fastboot_job.pipeline.find_all_actions(RecoveryBootAction)

        enter_mode = enter.pipeline.find_action(SwitchRecoveryCommand)
        recovery = fastboot_job.device["actions"]["deploy"]["methods"]["recovery"]
        self.assertIsNotNone(recovery["commands"].get(enter_mode.mode))
        self.assertEqual(
            [
                "/home/neil/lava-lab/shared/lab-scripts/eth008_control "
                "-a 10.15.0.171 -r 1 -s off",
                "/home/neil/lava-lab/shared/lab-scripts/eth008_control "
                "-a 10.15.0.171 -r 2 -s on",
            ],
            recovery["commands"][enter_mode.mode],
        )
        self.assertEqual("recovery_mode", enter_mode.mode)

        exit_mode = exit.pipeline.find_action(SwitchRecoveryCommand)
        self.assertIsNotNone(recovery["commands"].get(exit_mode.mode))
        self.assertEqual(
            [
                "/home/neil/lava-lab/shared/lab-scripts/eth008_control "
                "-a 10.15.0.171 -r 1 -s on",
                "/home/neil/lava-lab/shared/lab-scripts/eth008_control "
                "-a 10.15.0.171 -r 2 -s off",
            ],
            recovery["commands"][exit_mode.mode],
        )
        self.assertEqual("recovery_exit", exit_mode.mode)

    def test_uboot_commands(self):
        uboot_job = self.create_uboot_job()

        enter, exit = uboot_job.pipeline.find_all_actions(RecoveryBootAction)

        enter_mode = enter.pipeline.find_action(SwitchRecoveryCommand)
        recovery = uboot_job.device["actions"]["deploy"]["methods"]["recovery"]
        self.assertIsNotNone(recovery["commands"].get(enter_mode.mode))
        self.assertEqual(
            [
                "/usr/local/lab-scripts/eth008_control -a 192.168.0.32 -r 1 -s off",
                "/usr/local/lab-scripts/eth008_control -a 192.168.0.32 -r 2 -s off",
                "/usr/local/lab-scripts/eth008_control -a 192.168.0.32 -r 3 -s off",
                "/usr/local/lab-scripts/eth008_control -a 192.168.0.32 -r 4 -s off",
            ],
            recovery["commands"][enter_mode.mode],
        )
        self.assertEqual("recovery_mode", enter_mode.mode)

        exit_mode = exit.pipeline.find_action(SwitchRecoveryCommand)
        self.assertIsNotNone(recovery["commands"].get(exit_mode.mode))
        self.assertEqual(
            [
                "/usr/local/lab-scripts/eth008_control -a 192.168.0.32 -r 1 -s on",
                "/usr/local/lab-scripts/eth008_control -a 192.168.0.32 -r 2 -s on",
                "/usr/local/lab-scripts/eth008_control -a 192.168.0.32 -r 3 -s on",
                "/usr/local/lab-scripts/eth008_control -a 192.168.0.32 -r 4 -s on",
            ],
            recovery["commands"][exit_mode.mode],
        )
        self.assertEqual("recovery_exit", exit_mode.mode)
