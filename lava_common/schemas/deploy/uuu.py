#
# Copyright 2019-2020 NXP
#
# Author: Thomas Mahe <thomas.mahe@nxp.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import All, Any, Length, Optional, Range, Required

from lava_common.schemas import deploy


def schema():
    base = {
        Required("to"): "uuu",
        Required("images"): All(
            {
                Required("boot"): deploy.url(),
                Any(str): deploy.url(
                    {
                        Optional("apply-overlay"): bool,
                        Optional("root_partition"): Range(min=0),
                    }
                ),
            },
            Length(min=1),
        ),
    }
    return {**deploy.schema(), **base}
