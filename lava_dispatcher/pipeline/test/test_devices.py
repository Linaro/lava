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

from lava_dispatcher.pipeline.test.test_basic import Factory
from lava_dispatcher.tests.helper import LavaDispatcherTestCase
from lava_dispatcher.pipeline.device import DeviceTypeParser, NewDevice

# Test the loading of test definitions within the deploy stage


class TestDeviceParser(LavaDispatcherTestCase):

    def setUp(self):
        super(TestDeviceParser, self).setUp()

    def test_parser(self):
        test_parser = DeviceTypeParser()
        self.assertIsInstance(test_parser, DeviceTypeParser)

    def test_new_device(self):
        kvm01 = NewDevice('kvm01')
        try:
            self.assertIsNotNone(kvm01.parameters['actions'])
        except:
            self.fail("missing actions block for device")
        try:
            self.assertIsNotNone(kvm01.parameters['actions']['boot'])
        except:
            self.fail("missing boot block for device")
        try:
            self.assertIsNotNone(kvm01.parameters['actions']['deploy'])
        except:
            self.fail("missing boot block for device")
        self.assertTrue('qemu' in kvm01.parameters['actions']['boot']['methods'])
        self.assertTrue('image' in kvm01.parameters['actions']['deploy']['methods'])
