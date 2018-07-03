# Copyright (C) 2018 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
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
from lava_dispatcher.test.test_basic import Factory, StdoutTestCase
from lava_dispatcher.test.utils import infrastructure_error


class UBootUMSFactory(Factory):  # pylint: disable=too-few-public-methods
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """
    def create_warp7_job(self, filename):
        return self.create_job('imx7s-warp-01.jinja2', filename)


class TestUbootUMSAction(StdoutTestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super().setUp()
        self.factory = UBootUMSFactory()

    @unittest.skipIf(infrastructure_error('dd'), "dd not installed")
    def test_ums_action(self):
        job = self.factory.create_warp7_job('sample_jobs/warp7-ums.yaml')
        self.assertIsNotNone(job)

        description_ref = self.pipeline_reference('uboot-ums.yaml', job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))

        self.assertIsNone(job.validate())
        uboot = [action for action in job.pipeline.actions if action.name == 'uboot-action'][0]
        retry = [action for action in uboot.internal_pipeline.actions if action.name == 'uboot-retry'][0]
        flash = [action for action in retry.internal_pipeline.actions if action.name == 'flash-uboot-ums'][0]
        self.assertEqual("ums", flash.parameters['commands'])
        self.assertEqual("/dev/disk/by-id/usb-Linux_UMS_disk_0_WaRP7-0x742400d3000000e6-0:0", flash.usb_mass_device)
