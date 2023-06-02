#
# Copyright (C) 2018 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Msg, Optional, Required

from lava_common.schemas import boot, docker


def qemu_docker():
    return {**docker(), Optional("binary"): str}


def schema():
    base = {
        Required("method"): Msg("qemu", "'method' should be 'qemu'"),
        Optional("connection"): "serial",  # FIXME: is this needed or required?
        Optional("media"): "tmpfs",
        Optional("prompts"): boot.prompts(),
        Optional("transfer_overlay"): boot.transfer_overlay(),
        Optional(
            "auto_login"
        ): boot.auto_login(),  # TODO: if auto_login => prompt is required
        Optional("docker"): qemu_docker(),
    }
    return {**boot.schema(), **base}
