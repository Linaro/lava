#
# Copyright (C) 2019 Arm Limited
#
# Author: Chase Qi <chase.qi@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Msg, Optional, Required

from lava_common.schemas import boot, docker


def schema():
    base = {
        Required("method"): Msg("avh", "'method' should be 'avh'"),
        Optional("bootargs"): {
            Optional("normal"): str,
            Optional("restore"): str,
        },
        Optional("docker"): docker(),
        Required("prompts"): boot.prompts(),
        Optional("auto_login"): boot.auto_login(),
    }
    return {**boot.schema(), **base}
