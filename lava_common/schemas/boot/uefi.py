#
# Copyright (C) 2018 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Any, Msg, Optional, Required

from lava_common.schemas import boot


def schema():
    base = {
        Required("method"): Msg("uefi", "'method' should be 'uefi'"),
        Required("commands"): Any(str, [str]),
        Optional("shell_menu"): str,
        Optional("prompts"): boot.prompts(),
        Optional(
            "auto_login"
        ): boot.auto_login(),  # TODO: if auto_login => prompt is required
    }
    return {**boot.schema(), **base}
