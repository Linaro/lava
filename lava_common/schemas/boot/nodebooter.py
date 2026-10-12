# Copyright (C) 2023 Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Msg, Optional, Required

from lava_common.schemas import boot, docker


def schema():
    base = {
        Required("method"): Msg("nodebooter", "'method' should be 'nodebooter'"),
        Required("docker"): docker(),
        Optional("prompts"): boot.prompts(),
        Optional(
            "auto_login"
        ): boot.auto_login(),  # TODO: if auto_login => prompt is required
        Optional("transfer_overlay"): boot.transfer_overlay(),
    }
    return {**boot.schema(), **base}
