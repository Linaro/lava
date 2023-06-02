#
# Copyright (C) 2019 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Any, Msg, Required

from lava_common.schemas import boot


def schema():
    base = {
        Required("method"): Msg("recovery", "'method' should be 'recovery'"),
        Required("commands"): Any("recovery", "exit"),
    }
    return {**boot.schema(), **base}
