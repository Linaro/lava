#
# Copyright (C) 2018 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Optional, Required

from lava_common.schemas import deploy


def schema():
    extra = {
        Optional("format"): "qcow2",
        Optional("image_arg"): str,  # TODO: is this optional?
    }

    base = {
        Required("to"): "tmpfs",
        Required("images"): {Required(str, "'images' is empty"): deploy.url(extra)},
        Optional("type"): "monitor",
        Optional("uefi"): deploy.url(),  # TODO: check the exact syntax
    }
    return {**deploy.schema(), **base}
