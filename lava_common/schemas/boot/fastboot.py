#
# Copyright (C) 2018 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Msg, Optional, Required

from lava_common.schemas import boot, docker


def schema():
    base = {
        Required("method"): Msg("fastboot", "'method' should be 'fastboot'"),
        Optional("commands"): [str],
        Optional("use_bootscript"): bool,
        Optional("prompts"): boot.prompts(),
        Optional(
            "auto_login"
        ): boot.auto_login(),  # TODO: if auto_login => prompt is required
        Optional("transfer_overlay"): boot.transfer_overlay(),
        Optional("docker"): docker(),
    }
    return {**boot.schema(), **base}
