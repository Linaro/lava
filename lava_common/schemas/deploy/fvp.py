#
# Copyright (C) 2019 Arm Limited
#
# Author: Dean Birch <dean.birch@arm.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Optional, Required

from lava_common.schemas import deploy


def schema():
    base = {
        Required("to"): "fvp",
        Optional("ramdisk"): {
            Optional("install_overlay"): bool,
            Optional("compression"): str,
            Optional("header"): "u-boot",
        },
        Optional("uniquify"): bool,
        Required("images"): {Required(str, "'images' is empty"): deploy.url()},
    }
    return {**deploy.schema(), **base}
