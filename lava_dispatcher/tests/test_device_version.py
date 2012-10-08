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

from unittest import TestCase
import re
from lava_dispatcher.tests.helper import LavaDispatcherTestCase, create_device_config

from lava_dispatcher.device.target import Target
from lava_dispatcher.device.qemu import QEMUTarget
from lava_dispatcher.device.fastmodel import FastModelTarget

def _create_fastmodel():
    config = create_device_config('fastmodel01', { 'device_type': 'fastmodel', 'simulator_binary': '/path/to/fastmodel', 'license_server': 'foo.local' })
    target = FastModelTarget(None, config)
    return target

class TestDeviceVersion(LavaDispatcherTestCase):

    def test_base(self):
        target = Target(None, None)
        assert(type(target.get_device_version()) is str)

    def test_qemu(self):
        target = QEMUTarget(None, None)
        device_version = target.get_device_version()
        assert(re.search('^[0-9.]+', device_version))

    def test_fastmodel(self):
        banner = "\n".join([
            "Fast Models [7.1.36 (May 17 2012)]",
            "Copyright 2000-2012 ARM Limited.",
            "All Rights Reserved.",
            "Top component name: RTSM_VE_Cortex_A15x1_A7x1"
            ])
        target = _create_fastmodel()
        version = target._parse_fastmodel_version(banner)
        self.assertEqual('7.1.36', version)

    def test_fastmodel_wrong_format(self):
        client = _create_fastmodel()
        version = client._parse_fastmodel_version('random string')
        self.assertEqual('unknown', version)

