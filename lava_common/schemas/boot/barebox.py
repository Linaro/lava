#
# Copyright (C) 2019 Pengutronix e.K.
#
# Author: Michael Grzeschik <m.grzeschik@pengutronix.de>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Any, Msg, Optional, Required

from lava_common.schemas import boot


def schema():
    base = {
        Required("method"): Msg("barebox", "'method' should be 'barebox'"),
        Required("commands"): Any(str, [str]),
        Optional("prompts"): boot.prompts(),
        Optional(
            "auto_login"
        ): boot.auto_login(),  # TODO: if auto_login => prompt is required
        Optional("transfer_overlay"): boot.transfer_overlay(),
    }
    return {**boot.schema(), **base}
