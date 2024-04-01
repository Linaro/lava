# Copyright (C) 2017 Linaro Limited
#
# Author: Dean Birch <dean.birch@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from lava_dispatcher.actions.boot import (
    BootloaderCommandOverlay,
    BootloaderCommandsAction,
)
from lava_dispatcher.actions.boot.uefi import (
    UefiShellAction,
    UefiShellInterrupt,
    UefiShellMenuInterrupt,
    UefiShellMenuSelector,
)
from lava_dispatcher.actions.deploy.nfs import NfsAction
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.menus.menus import MenuConnect
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase


class TestUefiShell(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.factory = Factory()
        self.job = self.factory.create_job(
            "juno-r2-01", "sample_jobs/juno-uefi-nfs.yaml"
        )

    def test_shell_reference(self):
        self.job.validate()
        self.assertEqual([], self.job.pipeline.errors)
        description_ref = self.pipeline_reference("juno-uefi-nfs.yaml", job=self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe())

    def test_device_juno_uefi(self):
        job = self.job
        self.assertIsNotNone(job)
        self.assertIsNone(job.validate())

    def test_shell_prompts(self):
        self.job.validate()
        params = self.job.device["actions"]["boot"]["methods"]["uefi"]["parameters"]
        self.assertIn("shell_interrupt_prompt", params)
        self.assertIn("shell_menu", params)
        self.assertIn("bootloader_prompt", params)
        # Nfs Deploy checks
        deploy = self.job.pipeline.find_action(NfsAction)
        deploy.pipeline.find_action(OverlayAction)

        # Boot checks
        boot = self.job.pipeline.find_action(UefiShellAction)
        commands = boot.pipeline.find_action(BootloaderCommandOverlay)
        menu_connect = boot.pipeline.find_action(MenuConnect)
        menu_interrupt = boot.pipeline.find_action(UefiShellMenuInterrupt)
        menu_selector = boot.pipeline.find_action(UefiShellMenuSelector)
        boot_commands = boot.pipeline.find_action(BootloaderCommandsAction)
        self.assertEqual("uefi", commands.method)
        self.assertFalse(commands.use_bootscript)
        self.assertIsNone(commands.lava_mac)
        self.assertIsNotNone(menu_connect)
        self.assertIn("bootloader_prompt", menu_interrupt.params)
        self.assertIn("interrupt_prompt", menu_interrupt.params)
        self.assertIn("boot_message", menu_interrupt.params)
        # First, menu drops to shell...
        self.assertEqual("UEFI Interactive Shell", menu_selector.boot_message)
        # ...then, shell commands boot to linux.
        self.assertEqual("Linux version", boot_commands.params["boot_message"])

    def test_no_menu_reference(self):
        job = self.factory.create_job(
            "juno-r2-01", "sample_jobs/juno-uefi-nfs-no-menu.yaml"
        )
        self.assertEqual([], job.pipeline.errors)
        description_ref = self.pipeline_reference("juno-uefi-nfs-no-menu.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

    def test_no_menu(self):
        """
        Tests that if shell_menu=='' that the menu is skipped
        """
        job = self.factory.create_job(
            "juno-r2-01", "sample_jobs/juno-uefi-nfs-no-menu.yaml"
        )
        job.validate()
        params = job.device["actions"]["boot"]["methods"]["uefi"]["parameters"]
        self.assertIn("shell_interrupt_prompt", params)
        self.assertIn("shell_menu", params)
        self.assertIn("bootloader_prompt", params)
        # Nfs Deploy checks
        deploy = job.pipeline.find_action(NfsAction)
        deploy.pipeline.find_action(OverlayAction)

        # Boot checks
        boot = job.pipeline.find_action(UefiShellAction)
        commands = boot.pipeline.find_action(BootloaderCommandOverlay)
        boot_commands = boot.pipeline.find_action(BootloaderCommandsAction)
        boot.pipeline.find_action(UefiShellInterrupt)

        self.assertEqual(
            0,
            len(boot.pipeline.find_all_actions(UefiShellMenuInterrupt)),
        )
        self.assertEqual(
            0,
            len(boot.pipeline.find_all_actions(UefiShellMenuSelector)),
        )

        self.assertEqual("uefi", commands.method)
        self.assertFalse(commands.use_bootscript)
        self.assertIsNone(commands.lava_mac)

        # Shell commands boot to linux.
        self.assertEqual("Linux version", boot_commands.params["boot_message"])
