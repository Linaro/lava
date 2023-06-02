#
# Copyright (C) 2019 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Msg, Optional, Required

from lava_common.schemas import boot


def schema():
    base = {
        Required("method"): Msg("schroot", "'method' should be 'schroot'"),
        Optional("prompts"): boot.prompts(),
        Required("connection"): "ssh",
        Required("schroot"): str,
    }
    return {**boot.schema(), **base}
