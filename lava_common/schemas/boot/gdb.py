#
# Copyright (C) 2018 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Msg, Optional, Required

from lava_common.schemas import boot


def schema():
    base = {
        Required("method"): Msg("gdb", "'method' should be 'gdb'"),
        Required("commands"): str,
        Optional("container"): str,
    }
    return {**boot.schema(), **base}
