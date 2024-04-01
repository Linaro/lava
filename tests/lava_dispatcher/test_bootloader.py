# Copyright (C) 2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from lava_common.exceptions import InfrastructureError
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
