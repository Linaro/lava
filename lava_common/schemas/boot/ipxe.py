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
        Required("method"): Msg("ipxe", "'method' should be 'ipxe'"),
        Required("commands"): Any(str, [str]),
        Optional("prompts"): boot.prompts(),
        Optional("transfer_overlay"): boot.transfer_overlay(),
        Optional(
            "auto_login"
        ): boot.auto_login(),  # TODO: if auto_login => prompt is required
        Optional("use_bootscript"): bool,
    }
    return {**boot.schema(), **base}
