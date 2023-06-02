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
        Required("method"): Msg("kexec", "'method' should be 'kexec'"),
        Required("boot_message"): str,
        Optional("prompts"): boot.prompts(),
        Optional(
            "auto_login"
        ): boot.auto_login(),  # TODO: if auto_login => prompt is required
        Optional("deploy"): bool,
        Optional("command"): str,
        Optional("kernel"): str,
        Optional("dtb"): str,
        Optional("initrd"): str,
        Optional("options"): [str],
        Optional("kernel-config"): str,
        Optional("transfer_overlay"): boot.transfer_overlay(),
        Optional("on_panic"): bool,
    }
    return {**boot.schema(), **base}
