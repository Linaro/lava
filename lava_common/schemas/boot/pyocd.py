#
# Copyright (C) 2018 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Msg, Required

from lava_common.schemas import boot


def schema():
    base = {Required("method"): Msg("pyocd", "'method' should be 'pyocd'")}
    return {**boot.schema(), **base}
