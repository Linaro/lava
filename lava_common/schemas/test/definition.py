#
# Copyright (C) 2018-2019 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import Any, Match, Optional, Required

from lava_common.schemas import test
from lava_common.schemas.test.testdef import testdef


def schema():
    common = {
        Required("path"): str,
        Required("name"): Match(r"^[-_a-zA-Z0-9.]+$"),
        Optional("skip_install"): [
            Any("keys", "sources", "deps", "steps", "git-repos", "all")
        ],
        # Optional("parameters"):
        Optional("lava-signal"): Any("kmsg", "stdout"),
    }

    base = {
        Required("definitions"): [
            Any(
                {
                    Required("repository"): str,
                    Required("from"): "git",
                    Optional("branch"): str,
                    Optional("history"): bool,
                    Optional("revision"): str,
                    Optional("parameters"): dict,
                    Optional("params"): dict,
                    **common,
                },
                {
                    Required("repository"): str,
                    Required("from"): "url",
                    Optional("compression"): str,
                    Optional("parameters"): dict,
                    Optional("params"): dict,
                    **common,
                },
                {
                    Required("repository"): {**testdef()},
                    Required("from"): "inline",
                    **common,
                },
            )
        ]
    }
    return {**test.schema(), **base}
