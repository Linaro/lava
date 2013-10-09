# Copyright (C) 2011 Linaro Limited
#
# Author: Linaro Validation Team <linaro-dev@lists.linaro.org>
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

import lava_dispatcher.config
from lava_dispatcher.config import get_config, get_device_config
from lava_dispatcher.utils import string_to_list

from lava_dispatcher.tests.helper import *


class TestConfigData(LavaDispatcherTestCase):

    def test_server_ip(self):
        create_config('lava-dispatcher.conf', {'LAVA_SERVER_IP': '99.99.99.99'})
        server_config = get_config()
        expected = "99.99.99.99"
        lava_server_ip = server_config.lava_server_ip
        self.assertEqual(expected, lava_server_ip)
