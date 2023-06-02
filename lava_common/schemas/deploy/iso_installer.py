#
# Copyright (C) 2018 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Optional, Required

from lava_common.schemas import deploy


def schema():
    base = {
        Required("to"): "iso-installer",
        Required("images"): {
            Required("iso"): deploy.url(
                {Optional("image_arg"): str}  # TODO: is this optional?
            ),
            Required("preseed"): deploy.url(),
        },
        Required("iso"): {
            Required("installation_size"): str,
            Optional("kernel"): str,
            Optional("initrd"): str,
        },
    }
    return {**deploy.schema(), **base}
