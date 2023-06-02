#
# Copyright (C) 2019 Linaro Limited
#
# Author: Vincent Wan <vincent.wan@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Msg, Required

from lava_common.schemas import boot


def schema():
    base = {Required("method"): Msg("openocd", "'method' should be 'openocd'")}
    return {**boot.schema(), **base}
