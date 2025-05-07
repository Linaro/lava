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
        Required("to"): "flasher",
        Required("images"): {str: deploy.url()},
        Optional("uniquify"): bool,
    }
    return {**deploy.schema(), **base}
