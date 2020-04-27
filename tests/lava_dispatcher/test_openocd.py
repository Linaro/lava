# Copyright (C) 2019 Linaro Limited
#
# Author: Vincent Wan <vincent.wan@linaro.org>
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


import unittest
from tests.utils import infrastructure_error
from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase
from lava_common.exceptions import InfrastructureError
from lava_dispatcher.utils.shell import which


def check_openocd():
    try:
        which("openocd")
        return False
    except InfrastructureError:
        return True


class OpenOCDFactory(Factory):
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    @unittest.skipIf(infrastructure_error("openocd"), "openocd not installed")
    def create_cc3230SF_job(self, filename):
        return self.create_job("cc3220SF-02.jinja2", filename)


class TestOpenOCDAction(StdoutTestCase):
    @unittest.skipIf(check_openocd(), "openocd not available")
    def test_openocd_pipeline(self):
        factory = OpenOCDFactory()
        job = factory.create_cc3230SF_job("sample_jobs/cc3220SF-openocd.yaml")
        job.validate()
        description_ref = self.pipeline_reference("openocd.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))

        # Check BootOpenOCDRetry action
        action = job.pipeline.actions[1].pipeline.actions[0]
        self.assertEqual(action.name, "boot-openocd-image")

        # Check ConnectDevice action
        action = job.pipeline.actions[1].pipeline.actions[0].pipeline.actions[0]
        self.assertEqual(action.name, "connect-device")

        # Check FlashOpenOCDAction
        action = job.pipeline.actions[1].pipeline.actions[0].pipeline.actions[1]
        self.assertEqual(action.name, "flash-openocd")
        self.assertEqual(len(action.base_command), 24)
        print(action.base_command)
        self.assertEqual(action.base_command[0], "openocd")
        self.assertEqual(action.base_command[1], "-f")
        self.assertEqual(action.base_command[2], "board/ti_cc3220sf_launchpad.cfg")
        self.assertEqual(action.base_command[5], "-d2")
        self.assertEqual(action.base_command[23], "shutdown")
