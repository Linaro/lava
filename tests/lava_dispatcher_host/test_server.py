#
# Copyright (C) 2021 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import struct

import pytest

from lava_dispatcher_host.server import CommandHandler, ServerWrapper, ShareCommand


def make_writer(mocker, uid):
    # CPython returns an int when buflen is missing, which is what used to
    # crash struct.unpack; keep the quirk so the regression fails here.
    def getsockopt(level, optname, buflen=None):
        if buflen is None:
            return 1234
        return struct.pack("iii", 42, uid, uid)  # kernel order: pid, uid, gid

    sock = mocker.Mock()
    sock.getsockopt.side_effect = getsockopt
    writer = mocker.Mock()
    writer.transport.get_extra_info.return_value = sock
    return writer


class TestIsRootPeer:
    def test_root_peer(self, mocker):
        assert ServerWrapper()._is_root_peer(make_writer(mocker, 0)) is True

    def test_non_root_peer(self, mocker):
        assert ServerWrapper()._is_root_peer(make_writer(mocker, 1000)) is False

    def test_no_socket(self, mocker):
        writer = mocker.Mock()
        writer.transport.get_extra_info.return_value = None
        assert ServerWrapper()._is_root_peer(writer) is False


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
