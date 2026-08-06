# Copyright (C) 2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from lava_common.exceptions import InfrastructureError
from lava_dispatcher.actions.boot import BootloaderCommandsAction
from lava_dispatcher.actions.boot.bootloader import BootBootloaderAction
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase


class BootloaderFactory(Factory):
    def create_bootloader_job(self, filename):
        return self.create_job("b2260-01", filename)


class TestBootBootloader(LavaDispatcherTestCase):
    def test_pipeline(self):
        factory = BootloaderFactory()
        job = factory.create_bootloader_job("sample_jobs/b2260-bootloader.yaml")
        job.validate()
        description_ref = self.pipeline_reference("b2260-bootloader.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

        bootload_commands = (
            job.pipeline.actions[0].pipeline.actions[1].pipeline.actions[3]
        )
        self.assertEqual(bootload_commands.name, "bootloader-commands")
        self.assertEqual(bootload_commands.timeout.exception, InfrastructureError)

    def test_reset_connection_false(self):
        factory = BootloaderFactory()
        job = factory.create_bootloader_job("sample_jobs/b2260-bootloader.yaml")

        boot_retry_action = job.pipeline.actions[0]
        boot_action = boot_retry_action.pipeline.actions[1]
        boot_action.parameters["reset_connection"] = False

        boot_action.pipeline.actions = []
        boot_action.populate(boot_action.parameters)

        job.validate()

        # First action should be connect-device
        self.assertEqual(boot_action.pipeline.actions[0].name, "connect-device")

    def test_reset_device_false(self):
        factory = BootloaderFactory()
        job = factory.create_bootloader_job("sample_jobs/b2260-bootloader.yaml")

        boot_retry_action = job.pipeline.actions[0]
        boot_action = boot_retry_action.pipeline.actions[1]
        boot_action.parameters["reset_device"] = False

        boot_action.pipeline.actions = []
        boot_action.populate(boot_action.parameters)

        job.validate()

        action_names = [action.name for action in boot_action.pipeline.actions]

        # Should not contain reset-device
        self.assertNotIn("reset-device", action_names)

    def test_expect_final_default(self):
        factory = BootloaderFactory()
        job = factory.create_bootloader_job("sample_jobs/b2260-bootloader.yaml")

        boot_action = job.pipeline.actions[0].pipeline.actions[1]
        self.assertIsInstance(boot_action, BootBootloaderAction)
        self.assertFalse(boot_action.expect_final)

        bootloader_cmds = boot_action.pipeline.actions[-1]
        self.assertIsInstance(bootloader_cmds, BootloaderCommandsAction)
        self.assertFalse(bootloader_cmds.expect_final)

    def test_expect_final_true(self):
        factory = BootloaderFactory()
        job = factory.create_bootloader_job("sample_jobs/b2260-bootloader.yaml")

        boot_action = job.pipeline.actions[0].pipeline.actions[1]
        self.assertIsInstance(boot_action, BootBootloaderAction)

        new_action = BootBootloaderAction(job, expect_final=True)
        new_action.parameters = boot_action.parameters
        new_action.level = boot_action.level
        new_action.populate(boot_action.parameters)

        self.assertTrue(new_action.expect_final)
        bootloader_cmds = new_action.pipeline.actions[-1]
        self.assertIsInstance(bootloader_cmds, BootloaderCommandsAction)
        self.assertTrue(bootloader_cmds.expect_final)
