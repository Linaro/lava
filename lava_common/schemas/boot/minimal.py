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
        Required("method"): Msg("minimal", "'method' should be 'minimal'"),
        Optional("prompts"): boot.prompts(),
        Optional(
            "auto_login"
        ): boot.auto_login(),  # TODO: if auto_login => prompt is required
        Optional("pre_power_command"): bool,
        Optional("pre_os_command"): bool,
        Optional("reset"): bool,
        Optional("transfer_overlay"): boot.transfer_overlay(),
    }
    return {**boot.schema(), **base}
