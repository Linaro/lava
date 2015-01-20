# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
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
from lava_dispatcher.pipeline.action import Action
from lava_dispatcher.pipeline.device import DeviceTypeParser, NewDevice
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.boot import BootAction
from lava_dispatcher.pipeline.actions.boot.u_boot import UBootInterrupt, UBootAction

# Test the loading of test definitions within the deploy stage


class TestDeviceParser(unittest.TestCase):  # pylint: disable=too-many-public-methods

    def test_parser(self):
        test_parser = DeviceTypeParser()
        self.assertIsInstance(test_parser, DeviceTypeParser)

    def test_new_device(self):
        kvm01 = NewDevice('kvm01')
        try:
            self.assertIsNotNone(kvm01.parameters['actions'])
        except:  # pylint: disable=bare-except
            self.fail("missing actions block for device")
        try:
            self.assertIsNotNone(kvm01.parameters['actions']['boot'])
        except:  # pylint: disable=bare-except
            self.fail("missing boot block for device")
        try:
            self.assertIsNotNone(kvm01.parameters['actions']['deploy'])
        except:  # pylint: disable=bare-except
            self.fail("missing boot block for device")
        self.assertTrue('qemu' in kvm01.parameters['actions']['boot']['methods'])
        self.assertTrue('image' in kvm01.parameters['actions']['deploy']['methods'])


class FakeAction(Action):

    def __init__(self):
        super(FakeAction, self).__init__()
        self.name = "fake"
        self.description = "fake action for unit tests"
        self.summary = "fake action"


class TestJobDeviceParameters(unittest.TestCase):  # pylint: disable=too-many-public-methods
    """
    Test parsing of device configuration into job parameters
    """

    def test_device_parser(self):
        job_parser = JobParser()
        device = NewDevice('bbb-01')
        sample_job_file = os.path.join(os.path.dirname(__file__), 'sample_jobs/uboot-ramdisk.yaml')
        with open(sample_job_file) as sample_job_data:
            job = job_parser.parse(sample_job_data, device)
        uboot_action = None
        for action in job.pipeline.actions:
            if isinstance(action, DeployAction):
                self.assertIn('ramdisk', action.parameters)
            if isinstance(action, BootAction):
                self.assertIn('u-boot', action.parameters)
                self.assertIn('ramdisk', action.parameters['u-boot'])
                self.assertIn('bootloader_prompt', action.parameters['u-boot']['parameters'])
                self.assertIsNotNone(
                    action.parameters[
                        action.parameters['method']][
                            action.parameters['commands']]['commands']
                )
                for line in action.parameters[action.parameters['method']][action.parameters['commands']]['commands']:
                    self.assertIsNotNone(line)
                self.assertIsInstance(action, UBootAction)
                uboot_action = action
        self.assertIsNotNone(uboot_action)
        uboot_action.validate()
        self.assertTrue(uboot_action.valid)
        for action in uboot_action.internal_pipeline.actions:
            if isinstance(action, UBootInterrupt):
                self.assertIn('power_on', action.job.device.parameters['commands'])
                self.assertIn('hard_reset', action.job.device.parameters['commands'])
                self.assertIn('connect', action.job.device.parameters['commands'])
                self.assertEqual(action.job.device.parameters['commands']['connect'].split(' ')[0], 'telnet')
            if isinstance(action, UBootAction):
                self.assertIn('method', action.parameters)
                self.assertIn('commands', action.parameters)
                self.assertIn('ramdisk', action.parameters['u-boot'])
                self.assertIn(action.parameters['commands'], action.parameters[action.parameters['method']])
                self.assertIn('commands', action.parameters[action.parameters['method']][action.parameters['commands']])
                self.assertIsNotNone(action.parameters['u-boot']['ramdisk'])
                self.assertTrue(type(action.parameters['u-boot']['ramdisk']['commands']) == list)
                self.assertTrue(len(action.parameters['u-boot']['ramdisk']['commands']) > 2)

    def test_device_power(self):
        device = NewDevice("bbb-01")
        self.assertEqual(device.power_state, 'off')
        self.assertNotEqual(device.hard_reset_command, '')
        self.assertNotEqual(device.power_command, '')
        self.assertIn('on', device.power_command)
        device.power_state = 'on'
        self.assertEqual(device.power_state, 'on')
        device = NewDevice("kvm01")
        self.assertEqual(device.power_state, '')
        self.assertEqual(device.hard_reset_command, '')
        self.assertEqual(device.power_command, '')
        with self.assertRaises(RuntimeError):
            device.power_state = ''
        self.assertEqual(device.power_command, '')
