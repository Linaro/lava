#
# Copyright (C) 2019 Arm Limited
#
# Author: Dean Birch <dean.birch@arm.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Required

from lava_common.schemas import deploy


def schema():
    base = {
        Required("to"): "musca",
        Required("images"): {
            Required("test_binary", "'images' has no 'test_binary' entry"): deploy.url()
        },
    }
    return {**deploy.schema(), **base}
