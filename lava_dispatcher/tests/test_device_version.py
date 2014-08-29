# Copyright (C) 2012 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
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
# along with this program; if not, see <http://www.gnu.org/licenses>.

import re
from lava_dispatcher.tests.helper import LavaDispatcherTestCase, create_device_config, create_config
import os

from lava_dispatcher.device.target import Target
from lava_dispatcher.device.qemu import QEMUTarget
from lava_dispatcher.device.fastmodel import FastModelTarget
from lava_dispatcher.context import LavaContext
from lava_dispatcher.config import get_config


def _create_fastmodel_target():
    config = create_device_config('fastmodel01', {'device_type': 'fastmodel',
                                                  'simulator_binary': '/path/to/fastmodel',
                                                  'license_server': 'foo.local'})
    target = FastModelTarget(None, config)
    return target


def _create_qemu_target(extra_device_config={}):
    create_config('lava-dispatcher.conf', {})

    device_config_data = {'device_type': 'qemu'}
    device_config_data.update(extra_device_config)
    device_config = create_device_config('qemu01', device_config_data)

    dispatcher_config = get_config()

    context = LavaContext('qemu01', dispatcher_config, None, None, None)
    return QEMUTarget(context, device_config)


class TestDeviceVersion(LavaDispatcherTestCase):

    def test_base(self):
        target = Target(None, None)
        self.assertIsInstance(target.get_device_version(), str)

    def test_qemu(self):
        fake_qemu = os.path.join(os.path.dirname(__file__), 'test-config', 'bin', 'fake-qemu')
        target = _create_qemu_target({'qemu_binary': fake_qemu})
        device_version = target.get_device_version()
        assert(re.search('^[0-9.]+', device_version))


class TestDevice(LavaDispatcherTestCase):

    def setUp(self):
        super(TestDevice, self).setUp()
        self.target = Target(None, None)

    def test_boot_cmds_preprocessing_empty_list(self):
        boot_cmds = []
        expexted = []

        return_value = self.target._boot_cmds_preprocessing(boot_cmds)
        self.assertEqual(return_value, expexted)

    def test_boot_cmds_preprocessing(self):
        boot_cmds = ["foo", "bar", ""]
        expected = ["foo", "bar"]

        return_value = self.target._boot_cmds_preprocessing(boot_cmds)
        self.assertEqual(return_value, expected)
