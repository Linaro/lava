#
# Copyright (C) 2021 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import asyncio
import json
import struct

import pytest

from lava_common.exceptions import InfrastructureError
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


# What "devices share --remote" sends over the socket (see
# test_cmdline.py::test_share_device_remote). Spelled out here so both
# tests use the same field names.
SHARE_REQUEST = json.dumps(
    {
        "device": "foo/bar",
        "serial_number": "01234567890",
        "usb_vendor_id": None,
        "usb_product_id": None,
        "fs_label": None,
    }
).encode()


class TestHandleRequest:
    def run(self, mocker, request, uid=0):
        reader = mocker.Mock()
        reader.read = mocker.AsyncMock(return_value=request)
        writer = make_writer(mocker, uid)
        writer.drain = mocker.AsyncMock()
        writer.wait_closed = mocker.AsyncMock()
        asyncio.run(ServerWrapper().handle_request(reader, writer))
        return writer

    def result(self, writer):
        return json.loads(writer.write.call_args[0][0])

    def test_request_fields_reach_the_share(self, mocker, share_device_with_container):
        writer = self.run(mocker, SHARE_REQUEST)

        assert self.result(writer)["result"] == "OK"
        options = share_device_with_container.call_args[0][0]
        assert options.device == "foo/bar"
        assert options.serial_number == "01234567890"
        assert options.usb_vendor_id is None
        assert options.usb_product_id is None
        assert options.fs_label is None

    def test_malformed_request(self, mocker, share_device_with_container):
        writer = self.run(mocker, b"{not json")

        assert self.result(writer)["result"] == "INVALID_REQUEST"
        share_device_with_container.assert_not_called()

    def test_share_failure_is_reported(self, mocker, share_device_with_container):
        share_device_with_container.side_effect = InfrastructureError("no such device")
        writer = self.run(mocker, SHARE_REQUEST)

        assert self.result(writer)["result"] == "FAILED"
        assert "no such device" in self.result(writer)["message"]

    def test_non_root_peer_is_dropped(self, mocker, share_device_with_container):
        writer = self.run(mocker, SHARE_REQUEST, uid=1000)

        writer.write.assert_not_called()
        writer.close.assert_called_once()
        share_device_with_container.assert_not_called()
