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
    # from_device_file must raise a real exception (a bare MagicMock is not a
    # BaseException subclass and cannot be used in an except clause).
    p.DeviceNotFoundError = type("DeviceNotFoundError", (Exception,), {})
    # Make the mocked node's property lookups always match the mapping's
    # device_info so the self-consistency check does not reject in unit tests.
    p.Devices.from_device_file.return_value.properties.get.return_value = _AlwaysEqual()
    return p
