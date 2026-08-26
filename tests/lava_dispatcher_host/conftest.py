# Copyright (C) 2020 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pytest


class _AlwaysEqual:
    """Test shim: compares equal to anything, so the self-consistency check in
    share_device_with_container passes for the mocked node. The real udev
    attribute-matching is covered by a dedicated regression test."""

    def __eq__(self, other):
        return True


@pytest.fixture(autouse=True)
def pyudev(mocker):
    p = mocker.patch("lava_dispatcher_host.utils.pyudev")
    # DeviceNotFoundError must be a real exception (a bare MagicMock is not a
    # BaseException subclass and cannot be used in an except clause).
    p.DeviceNotFoundError = type("DeviceNotFoundError", (Exception,), {})
    # Default: list_devices() yields one node whose properties always match the
    # mapping's device_info, so the server-side node resolution does not reject
    # in unit tests. Tests that need a specific (or no) node override
    # context.list_devices.return_value.
    node = mocker.MagicMock()
    node.device_node = "/dev/mocknode"
    node.device_links = []
    node.properties.get.return_value = _AlwaysEqual()
    p.Context.return_value.list_devices.return_value = [node]
    # context is a module-level pyudev.Context() created at import time, so it
    # does not see the mocked pyudev module above. Patch its list_devices
    # directly so _resolve_nodes() resolves the mock node in unit tests.
    mocker.patch("lava_dispatcher_host.utils.context.list_devices", return_value=[node])
    return p
