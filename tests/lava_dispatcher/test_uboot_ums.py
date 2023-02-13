# Copyright (C) 2018 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import unittest

from tests.lava_dispatcher.test_basic import Factory, StdoutTestCase
from tests.utils import infrastructure_error


class UBootUMSFactory(Factory):
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    def create_warp7_job(self, filename):
        return self.create_job("imx7s-warp-01.jinja2", filename)


class TestUbootUMSAction(StdoutTestCase):
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
        uboot = [
            action for action in job.pipeline.actions if action.name == "uboot-action"
        ][0]
        retry = [
            action
            for action in uboot.pipeline.actions
            if action.name == "uboot-commands"
        ][0]
        flash = [
            action
            for action in retry.pipeline.actions
            if action.name == "flash-uboot-ums"
        ][0]
        self.assertEqual("ums", flash.parameters["commands"])
        self.assertEqual(
            "/dev/disk/by-id/usb-Linux_UMS_disk_0_WaRP7-0x742400d3000000e6-0:0",
            flash.usb_mass_device,
        )
