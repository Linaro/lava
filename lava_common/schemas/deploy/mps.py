#
# Copyright (C) 2019 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import All, Length, Match, Optional, Required

from lava_common.schemas import deploy


def schema():
    base = {
        Required("to"): "mps",
        Required("images"): All(
            {
                Optional("recovery_image"): deploy.url(),
                Optional(Match("test_binary(_\\w+)?$")): deploy.url(
                    {Optional("rename"): str}
                ),
            },
            Length(min=1),
        ),
    }
    return {**deploy.schema(), **base}
