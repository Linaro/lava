# Copyright (C) 2023 Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Msg, Optional, Required

from lava_common.schemas import boot


def schema():
    base = {
        Required("method"): Msg("nodebooter", "'method' should be 'nodebooter'"),
        Required("command"): str,
        Optional("prompts"): boot.prompts(),
        Optional("downloads-namespace"): str,
    }
    return {**boot.schema(), **base}
