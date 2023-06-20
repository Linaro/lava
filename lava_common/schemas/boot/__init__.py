#
# Copyright (C) 2018-2019 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import All, Any, Length, Optional, Required

from lava_common.schemas import action


def auto_login():
    return Any(
        {
            Required("login_prompt"): All(str, Length(min=1)),
            Required("username"): str,
            Optional("login_commands"): [All(str, Length(min=1))],
        },
        {
            Required("login_prompt"): All(str, Length(min=1)),
            Required("username"): str,
            Required("password_prompt"): str,
            Required("password"): str,
            Optional("login_commands"): [str],
            Optional("ignore_kernel_messages"): bool,
        },
    )


def transfer_overlay():
    return {
        Required("download_command"): str,
        Required("unpack_command"): str,
        Optional("transfer_method"): str,
    }


def prompts():
    # FIXME: prompts should only accept a list
    return Any(All(str, Length(min=1)), [All(str, Length(min=1))])


def schema():
    return {
        **action(),
        Optional("parameters"): {
            Optional("kernel-start-message"): str,
            Optional("shutdown-message"): str,
        },
        Optional("soft_reboot"): Any(str, [str]),
    }
