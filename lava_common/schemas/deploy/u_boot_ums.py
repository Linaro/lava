#
# Copyright (C) 2018 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Optional, Range, Required

from lava_common.schemas import deploy


def schema():
    base = {
        Required("to"): "u-boot-ums",
        Required("image"): deploy.url({Optional("root_partition"): Range(min=0)}),
    }
    return {**deploy.schema(), **base}
