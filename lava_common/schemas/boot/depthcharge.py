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
        Required("method"): Msg("depthcharge", "'method' should be 'depthcharge'"),
        Required("commands"): Any(str, [str]),
        Optional("extra_kernel_args"): str,
        Optional("auto_login"): boot.auto_login(),
        Optional("prompts"): boot.prompts(),
        Optional("use_bootscript"): bool,
        Optional("transfer_overlay"): boot.transfer_overlay(),
    }
    return {**boot.schema(), **base}
