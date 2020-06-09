# Copyright (C) 2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

from lava_common.exceptions import InfrastructureError
from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase


class BootloaderFactory(Factory):
    def create_bootloader_job(self, filename):
        return self.create_job("b2260-01.jinja2", filename)


class TestBootBootloader(StdoutTestCase):
    def test_pipeline(self):
        factory = BootloaderFactory()
        job = factory.create_bootloader_job("sample_jobs/b2260-bootloader.yaml")
        job.validate()
        description_ref = self.pipeline_reference("b2260-bootloader.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))

        bootload_commands = (
            job.pipeline.actions[0].pipeline.actions[1].pipeline.actions[3]
        )
        self.assertEqual(bootload_commands.name, "bootloader-commands")
        self.assertEqual(bootload_commands.timeout.exception, InfrastructureError)
