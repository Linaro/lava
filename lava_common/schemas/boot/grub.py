#
# Copyright (C) 2018-2019 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Any, Msg, Optional, Required

from lava_common.schemas import boot


def base_schema():
    return {
        Required("commands"): Any(str, [str]),
        Optional(
            "auto_login"
        ): boot.auto_login(),  # TODO: if auto_login => prompt is required
        Optional("boot_finished"): Any(str, [str]),
        Optional("expect_shell"): bool,
        Optional("prompts"): boot.prompts(),
        Optional("use_bootscript"): bool,
        Optional("transfer_overlay"): boot.transfer_overlay(),
    }


def schema():
    base = {
        Required("method"): Msg("grub", "'method' should be 'grub'"),
        **base_schema(),
    }
    return {**boot.schema(), **base}
