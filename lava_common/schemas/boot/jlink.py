#
# Copyright (C) 2019 Linaro Limited
#
# Author: Andrei Gansari <andrei.gansari@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Msg, Optional, Required

from lava_common.schemas import boot


def schema():
    base = {
        Required("method"): Msg("jlink", "'method' should be 'jlink'"),
        Optional("prompts"): [str],
        Optional("commands"): [str],
        Optional("coretype"): str,
    }
    return {**boot.schema(), **base}
