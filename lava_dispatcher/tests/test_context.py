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

from lava_dispatcher.client.fastmodel import LavaFastModelClient
from lava_dispatcher.client.master import LavaMasterImageClient
from lava_dispatcher.client.qemu import LavaQEMUClient
from lava_dispatcher.context import LavaContext

class TestContext(TestCase):

    def test_client_type_qemu(self):
        assert(LavaContext.get_client_class('qemu') is LavaQEMUClient)

    def test_client_type_master(self):
        assert(LavaContext.get_client_class('master') is LavaMasterImageClient)

    def test_client_type_fastmodel(self):
        assert(LavaContext.get_client_class('fastmodel') is LavaFastModelClient)
