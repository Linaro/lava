# Copyright (C) 2019 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later

from lava_dispatcher_host.udev import get_udev_rules


def test_get_udev_rules():
    rules = get_udev_rules()
    assert 'ACTION=="add"' in rules
