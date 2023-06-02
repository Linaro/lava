#
# Copyright (C) 2019 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Required

from lava_common.schemas import deploy


def schema():
    base = {
        Required("to"): "recovery",
        Required("images"): {Required(str, "'images' is empty"): deploy.url()},
    }
    return {**deploy.schema(), **base}
