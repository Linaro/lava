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
        Required("method"): Msg("qemu-nfs", "'method' should be 'qemu-nfs'"),
        Optional("connection"): "serial",  # FIXME: is this needed or required?
        Optional("prompts"): boot.prompts(),
        Optional("transfer_overlay"): boot.transfer_overlay(),
        Optional(
            "auto_login"
        ): boot.auto_login(),  # TODO: if auto_login => prompt is required
    }
    return {**boot.schema(), **base}
