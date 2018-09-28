# Copyright (C) 2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.


import os
import yaml
import unittest
from lava_dispatcher.test.test_basic import Factory, StdoutTestCase
from lava_dispatcher.device import NewDevice
from lava_dispatcher.parser import JobParser
from lava_dispatcher.test.utils import DummyLogger, infrastructure_error_multi_paths
from lava_dispatcher.utils.udev import allow_fs_label


class FastBootFactory(Factory):  # pylint: disable=too-few-public-methods
    """
    Not Model based, this is not a Django factory.
    Factory objects are dispatcher based classes, independent
    of any database objects.
    """

    def create_hikey_bl_device(self, hostname):
        """
        Create a device configuration on-the-fly from in-tree
        device-type Jinja2 template.
        """
        with open(
            os.path.join(
                os.path.dirname(__file__),
                '..', '..', 'lava_scheduler_app', 'tests',
                'devices', 'hi6220-hikey-bl-01.jinja2')) as hikey:
            data = hikey.read()
        test_template = self.prepare_jinja_template(hostname, data)
        rendered = test_template.render()
        return (rendered, data)

    def create_hikey_bl_job(self, filename):
        (data, device_dict) = self.create_hikey_bl_device('hi6220-hikey-01')
        device = NewDevice(yaml.safe_load(data))
        self.validate_data('hi6220-hikey-01', device_dict)
        fastboot_yaml = os.path.join(os.path.dirname(__file__), filename)
        with open(fastboot_yaml) as sample_job_data:
            parser = JobParser()
            job = parser.parse(sample_job_data, device, 4212, None, "")
            job.logger = DummyLogger()
        return job


class TestRecoveryMode(StdoutTestCase):  # pylint: disable=too-many-public-methods

    def setUp(self):
        super().setUp()
        self.factory = FastBootFactory()
        self.job = self.factory.create_hikey_bl_job('sample_jobs/hi6220-recovery.yaml')

    @unittest.skipIf(infrastructure_error_multi_paths(
        ['lxc-info', 'img2simg', 'simg2img']),
        "lxc or img2simg or simg2img not installed")
    def test_structure(self):
        self.assertIsNotNone(self.job)
        self.job.validate()

        description_ref = self.pipeline_reference('hi6220-recovery.yaml', job=self.job)
        self.assertEqual(description_ref, self.job.pipeline.describe(False))

        requires_board_id = not allow_fs_label(self.job.device)
        self.assertFalse(requires_board_id)
        if 'device_info' in self.job.device:
            for usb_device in self.job.device['device_info']:
                if usb_device.get('board_id', '') in ['', '0000000000'] \
                        and requires_board_id:
                    self.fail("[LXC_CREATE] board_id unset")

    def test_commands(self):
        enter = [action for action in self.job.pipeline.actions if action.name == 'recovery-boot'][0]
        mode = [action for action in enter.internal_pipeline.actions if action.name == 'switch-recovery'][0]
        recovery = self.job.device['actions']['deploy']['methods']['recovery']
        self.assertIsNotNone(recovery['commands'].get(mode.mode))
        self.assertEqual(
            [
                '/home/neil/lava-lab/shared/lab-scripts/eth008_control -a 10.15.0.171 -r 1 -s off',
                '/home/neil/lava-lab/shared/lab-scripts/eth008_control -a 10.15.0.171 -r 2 -s on'],
            recovery['commands'][mode.mode])
        self.assertEqual('recovery_mode', mode.mode)
        exit_mode = [action for action in self.job.pipeline.actions if action.name == 'recovery-boot'][1]
        mode = [action for action in exit_mode.internal_pipeline.actions if action.name == 'switch-recovery'][0]
        self.assertIsNotNone(recovery['commands'].get(mode.mode))
        self.assertEqual(
            [
                '/home/neil/lava-lab/shared/lab-scripts/eth008_control -a 10.15.0.171 -r 1 -s on',
                '/home/neil/lava-lab/shared/lab-scripts/eth008_control -a 10.15.0.171 -r 2 -s off'],
            recovery['commands'][mode.mode])
        self.assertEqual('recovery_exit', mode.mode)
