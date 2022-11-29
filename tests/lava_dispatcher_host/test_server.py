# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software; you can redistribute it and/or modify
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

import pytest

from lava_dispatcher_host.server import CommandHandler, ShareCommand


@pytest.fixture
def share_device_with_container(mocker):
    return mocker.patch("lava_dispatcher_host.server.share_device_with_container")


class TestCommandHandler:
    def test_basics(self, share_device_with_container):
        server = CommandHandler()
        server.handle(ShareCommand(device="/dev/foobar", serial="0123456789"))
        share_device_with_container.assert_called()
        options = share_device_with_container.call_args[0][0]
        assert options.device == "/dev/foobar"
        assert options.serial == "0123456789"
