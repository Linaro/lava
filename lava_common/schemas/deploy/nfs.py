#
# Copyright (C) 2019 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Any, Optional, Required

from lava_common.schemas import deploy


def schema():
    return Any(
        {
            Required("to"): "nfs",
            Optional("nfsrootfs"): deploy.url(),
            Optional("modules"): deploy.url(),
            **deploy.schema(),
        },
        {
            Required("to"): "nfs",
            Required("images"): {
                Required(str, "'images' is empty"): deploy.url(
                    {Optional("image_arg"): str}
                )
            },
            **deploy.schema(),
        },
    )
