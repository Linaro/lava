# Copyright (C) 2017 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from lava_dispatcher.power import PDUReboot, ResetDevice, SendRebootCommands
from tests.lava_dispatcher.test_basic import Factory, LavaDispatcherTestCase


class TestPowerAction(LavaDispatcherTestCase):
    def setUp(self):
        super().setUp()
        self.factory = Factory()

    def test_reset_nopower(self):
        job = self.factory.create_job("cubie1", "sample_jobs/uboot-ramdisk.yaml")
        reset_device = job.pipeline.find_action(ResetDevice)
        self.assertEqual(
            [SendRebootCommands],
            [type(a) for a in reset_device.pipeline.actions],
        )

    def test_reset_power(self):
        job = self.factory.create_job("bbb-01", "sample_jobs/uboot-ramdisk.yaml")
        reset_device = job.pipeline.find_action(ResetDevice)
        self.assertEqual(
            [PDUReboot],
            [type(a) for a in reset_device.pipeline.actions],
        )
