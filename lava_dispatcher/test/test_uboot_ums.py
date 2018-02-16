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

import os
import unittest
from lava_dispatcher.device import NewDevice
from lava_dispatcher.parser import JobParser
from lava_dispatcher.test.test_basic import Factory, StdoutTestCase
from lava_dispatcher.test.utils import DummyLogger
from lava_dispatcher.utils.shell import infrastructure_error


class UBootUMSFactory(Factory):  # pylint: disable=too-few-public-methods
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """
    def create_warp7_job(self, filename):  # pylint: disable=no-self-use
        device = NewDevice(os.path.join(os.path.dirname(__file__), '../devices/imx7s-warp-01.yaml'))
        bbb_yaml = os.path.join(os.path.dirname(__file__), filename)
        with open(bbb_yaml) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, device, 4212, None, "")
            job.logger = DummyLogger()
        return job


class TestUbootUMSAction(StdoutTestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super(TestUbootUMSAction, self).setUp()
        self.factory = UBootUMSFactory()

    @unittest.skipIf(infrastructure_error('dd'), "dd not installed")
    def test_ums_action(self):
        job = self.factory.create_warp7_job('sample_jobs/warp7-ums.yaml')
        self.assertIsNotNone(job)

        description_ref = self.pipeline_reference('uboot-ums.yaml', job=job)
        self.assertEqual(description_ref, job.pipeline.describe(False))

        self.assertIsNone(job.validate())
        self.assertEqual(job.device['device_type'], 'imx7s-warp')
        uboot = [action for action in job.pipeline.actions if action.name == 'uboot-action'][0]
        retry = [action for action in uboot.internal_pipeline.actions if action.name == 'uboot-retry'][0]
        flash = [action for action in retry.internal_pipeline.actions if action.name == 'flash-uboot-ums'][0]
        self.assertEqual("ums", flash.parameters['commands'])
        self.assertEqual("/dev/vde", flash.usb_mass_device)
