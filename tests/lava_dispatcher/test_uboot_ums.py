# Copyright (C) 2018 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import unittest

from lava_dispatcher.utils.storage import FlashUBootUMSAction
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase
from tests.utils import infrastructure_error


class UBootUMSFactory(Factory):
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    def create_warp7_job(self, filename):
        return self.create_job("imx7s-warp-01", filename)


class TestUbootUMSAction(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.factory = UBootUMSFactory()

    @unittest.skipIf(infrastructure_error("bmaptool"), "dd not installed")
    def test_ums_action(self):
        job = self.factory.create_warp7_job("sample_jobs/warp7-ums.yaml")
        self.assertIsNotNone(job)

        description_ref = self.pipeline_reference("uboot-ums.yaml", job=job)
        self.assertEqual(description_ref, job.pipeline.describe())

        self.assertIsNone(job.validate())

        flash = job.pipeline.find_action(FlashUBootUMSAction)
        self.assertEqual("ums", flash.parameters["commands"])
        self.assertEqual(
            "/dev/disk/by-id/usb-Linux_UMS_disk_0_WaRP7-0x742400d3000000e6-0:0",
            flash.usb_mass_device,
        )
