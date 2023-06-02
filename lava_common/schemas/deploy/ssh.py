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
        Required("to"): "ssh",
        Optional("firmware"): deploy.url(),
        Optional("kernel"): deploy.url(),
        Optional("rootfs"): deploy.url(),
        Optional("modules"): deploy.url(),
    }
    return {**deploy.schema(), **base}
