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
        Required("method"): Msg("bootloader", "'method' should be 'bootloader'"),
        Required("bootloader"): str,
        Required("commands"): [str],
        Optional("use_bootscript"): bool,
        Optional("prompts"): boot.prompts(),
    }
    return {**boot.schema(), **base}
