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
from lava_dispatcher.tests.helper import LavaClientTestCase, create_device_config

from lava_dispatcher.client.base import LavaClient
from lava_dispatcher.client.fastmodel import LavaFastModelClient
from lava_dispatcher.client.master import LavaMasterImageClient
from lava_dispatcher.client.qemu import LavaQEMUClient

class TestDeviceVersion(TestCase):

    def test_base(self):
        client = LavaClient(None, None)
        assert(type(client.device_version) is str)

    def test_qemu(self):
        client = LavaQEMUClient(None, None)
        device_version = client.device_version
        assert(re.search('^[0-9.]+', device_version))
