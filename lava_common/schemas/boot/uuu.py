#
# Copyright 2019-2020 NXP
#
# Author: Mahe Thomas <thomas.mahe@nxp.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Any, Msg, Optional, Required

from lava_common.schemas import boot, docker


def schema():
    base = {
        Required("method"): Msg("uuu", "'method' should be 'uuu'"),
        Required("commands"): Any(str, [{str: str}]),
        Optional("docker"): docker(),
    }
    return {**boot.schema(), **base}
