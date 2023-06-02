#
# Copyright (C) 2018 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Any, Match, Optional, Required

from lava_common.schemas import test


def schema():
    base = {
        Required("monitors"): [
            {
                Required("name"): Match(r"^[-_a-zA-Z0-9.]+$"),
                Required("start"): str,
                Required("end"): str,
                Required("pattern"): str,
                Optional("fixupdict"): {str: Any("pass", "fail", "skip", "unknown")},
            }
        ]
    }
    return {**test.schema(), **base}
