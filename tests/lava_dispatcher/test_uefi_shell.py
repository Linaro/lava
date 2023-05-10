# Copyright (C) 2017 Linaro Limited
#
# Author: Dean Birch <dean.birch@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase


class TestUefiShell(StdoutTestCase):
    def setUp(self):
        super().setUp()
        self.factory = Factory()
        self.job = self.factory.create_job(
            "juno-r2-01.jinja2", "sample_jobs/juno-uefi-nfs.yaml"
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
        deploy = [
            action
            for action in self.job.pipeline.actions
            if action.name == "nfs-deploy"
        ][0]
        overlay = [
            action
            for action in deploy.pipeline.actions
            if action.name == "lava-overlay"
        ][0]
        self.assertIsNotNone(overlay)

        # Boot checks
        boot = [
            action
            for action in self.job.pipeline.actions
            if action.name == "uefi-shell-main-action"
        ][0]
        commands = [
            action
            for action in boot.pipeline.actions
            if action.name == "bootloader-overlay"
        ][0]
        menu_connect = [
            action for action in boot.pipeline.actions if action.name == "menu-connect"
        ][0]
        menu_interrupt = [
            action
            for action in boot.pipeline.actions
            if action.name == "uefi-shell-menu-interrupt"
        ][0]
        menu_selector = [
            action
            for action in boot.pipeline.actions
            if action.name == "uefi-shell-menu-selector"
        ][0]
        shell_interrupt = [
            action
            for action in boot.pipeline.actions
            if action.name == "uefi-shell-menu-interrupt"
        ][0]
        boot_commands = [
            action
            for action in boot.pipeline.actions
            if action.name == "bootloader-commands"
        ][0]
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
        self.assertIsNotNone(shell_interrupt)

    def test_no_menu_reference(self):
        job = self.factory.create_job(
            "juno-r2-01.jinja2", "sample_jobs/juno-uefi-nfs-no-menu.yaml"
        )
        self.assertEqual([], job.pipeline.errors)
        description_ref = self.pipeline_reference("juno-uefi-nfs-no-menu.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

    def test_no_menu(self):
        """
        Tests that if shell_menu=='' that the menu is skipped
        """
        job = self.factory.create_job(
            "juno-r2-01.jinja2", "sample_jobs/juno-uefi-nfs-no-menu.yaml"
        )
        job.validate()
        params = job.device["actions"]["boot"]["methods"]["uefi"]["parameters"]
        self.assertIn("shell_interrupt_prompt", params)
        self.assertIn("shell_menu", params)
        self.assertIn("bootloader_prompt", params)
        # Nfs Deploy checks
        deploy = [
            action for action in job.pipeline.actions if action.name == "nfs-deploy"
        ][0]
        overlay = [
            action
            for action in deploy.pipeline.actions
            if action.name == "lava-overlay"
        ][0]
        self.assertIsNotNone(overlay)

        # Boot checks
        boot = [
            action
            for action in job.pipeline.actions
            if action.name == "uefi-shell-main-action"
        ][0]
        commands = [
            action
            for action in boot.pipeline.actions
            if action.name == "bootloader-overlay"
        ][0]
        boot_commands = [
            action
            for action in boot.pipeline.actions
            if action.name == "bootloader-commands"
        ][0]

        self.assertIsNotNone(
            [
                action
                for action in boot.pipeline.actions
                if action.name == "uefi-shell-interrupt"
            ]
        )

        self.assertEqual(
            0,
            len(
                [
                    action
                    for action in boot.pipeline.actions
                    if action.name == "uefi-shell-menu-interrupt"
                ]
            ),
        )
        self.assertEqual(
            0,
            len(
                [
                    action
                    for action in boot.pipeline.actions
                    if action.name == "uefi-shell-menu-selector"
                ]
            ),
        )

        self.assertEqual("uefi", commands.method)
        self.assertFalse(commands.use_bootscript)
        self.assertIsNone(commands.lava_mac)

        # Shell commands boot to linux.
        self.assertEqual("Linux version", boot_commands.params["boot_message"])
