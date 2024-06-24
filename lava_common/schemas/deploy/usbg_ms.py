#
# Copyright (C) 2024 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Required

from lava_common.schemas import deploy


def schema():
    return {
        Required("to"): "usbg-ms",
        Required("image"): deploy.url(),
        **deploy.schema(),
    }
