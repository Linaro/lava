# Copyright (C) 2017 Linaro Limited
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


from lava_dispatcher.tests.test_basic import Factory, StdoutTestCase


class TestPowerAction(StdoutTestCase):  # pylint: disable=too-many-public-methods
    def setUp(self):
        super().setUp()
        self.factory = Factory()

    def test_reset_nopower(self):
        job = self.factory.create_job("cubie1.jinja2", "sample_jobs/uboot-ramdisk.yaml")
        uboot_action = None
        names = [r_action.name for r_action in job.pipeline.actions]
        self.assertIn("uboot-action", names)
        uboot_action = [
            action for action in job.pipeline.actions if action.name == "uboot-action"
        ][0]
        names = [r_action.name for r_action in uboot_action.internal_pipeline.actions]
        self.assertIn("uboot-retry", names)
        uboot_retry = [
            action
            for action in uboot_action.pipeline.actions
            if action.name == "uboot-retry"
        ][0]
        names = [r_action.name for r_action in uboot_retry.internal_pipeline.actions]
        self.assertIn("reset-device", names)
        reset_device = [
            action
            for action in uboot_retry.pipeline.actions
            if action.name == "reset-device"
        ][0]
        names = [r_action.name for r_action in reset_device.internal_pipeline.actions]
        self.assertEqual(["send-reboot-commands"], names)

    def test_reset_power(self):
        job = self.factory.create_job("bbb-01.jinja2", "sample_jobs/uboot-ramdisk.yaml")
        uboot_action = None
        names = [r_action.name for r_action in job.pipeline.actions]
        self.assertIn("uboot-action", names)
        uboot_action = [
            action for action in job.pipeline.actions if action.name == "uboot-action"
        ][0]
        names = [r_action.name for r_action in uboot_action.internal_pipeline.actions]
        self.assertIn("uboot-retry", names)
        uboot_retry = [
            action
            for action in uboot_action.pipeline.actions
            if action.name == "uboot-retry"
        ][0]
        names = [r_action.name for r_action in uboot_retry.internal_pipeline.actions]
        self.assertIn("reset-device", names)
        reset_device = [
            action
            for action in uboot_retry.pipeline.actions
            if action.name == "reset-device"
        ][0]
        names = [r_action.name for r_action in reset_device.internal_pipeline.actions]
        self.assertEqual(["pdu-reboot"], names)
