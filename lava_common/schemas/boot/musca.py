#
# Copyright (C) 2019 Arm Limited
#
# Author: Dean Birch <dean.birch@arm.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Msg, Optional, Required

from lava_common.schemas import boot


def schema():
    base = {
        Required("method"): Msg("musca", "'method' should be 'musca'"),
        Optional("prompts"): boot.prompts(),
    }
    return {**boot.schema(), **base}
