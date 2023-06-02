#
# Copyright (C) 2021 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

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
