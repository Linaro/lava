#
# Copyright (C) 2019 Arm Limited
#
# Author: Dean Birch <dean.birch@arm.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Msg, Optional, Required

from lava_common.schemas import boot, docker


def schema():
    base = {
        Required("method"): Msg("fvp", "'method' should be 'fvp'"),
        Optional("use_telnet"): bool,
        Required("console_string"): str,
        Optional("feedbacks"): [str],
        Required("image"): str,
        Optional("license_variable"): str,
        Optional("ubl_license"): str,
        Optional("version_string"): str,
        Required("arguments"): [str],
        Required("prompts"): boot.prompts(),
        Required("docker"): docker("name"),
        Optional("transfer_overlay"): boot.transfer_overlay(),
        Optional("auto_login"): boot.auto_login(),
    }
    return {**boot.schema(), **base}
