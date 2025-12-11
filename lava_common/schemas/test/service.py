# Copyright (C) 2025 Linaro Limited
#
# Author: Chase Qi <chase.qi@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Any, Match, Optional, Required

from lava_common.schemas import test


def schema():
    common = {
        Required("name"): Match(r"^[-_a-zA-Z0-9.]+$"),
        Required("repository"): str,
        Required("path"): str,
        Optional("service"): str,
    }

    base = {
        Required("services"): [
            Any(
                {
                    Required("from"): "git",
                    Optional("branch"): str,
                    Optional("history"): bool,
                    Optional("revision"): str,
                    Optional("recursive"): bool,
                    **common,
                },
                {
                    Required("from"): "url",
                    Optional("compression"): str,
                    Optional("headers"): dict,
                    **common,
                },
            )
        ]
    }

    return {**test.schema(), **base}
