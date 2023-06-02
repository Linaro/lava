#
# Copyright (C) 2018 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import All, Any, Length, Match, Optional, Required

from lava_common.schemas import test


def schema():
    base = {
        Required("interactive"): [
            {
                Required("name"): Match(r"^[-_a-zA-Z0-9.]+$"),
                Required("prompts"): [All(str, Length(min=1))],
                Optional("echo"): "discard",
                Required("script"): [
                    {
                        Optional("command"): Any(str, None),
                        Optional("delay"): int,
                        Optional("lava-send"): str,
                        Optional("lava-sync"): str,
                        Optional("lava-wait"): str,
                        Optional("lava-wait-all"): str,
                        Optional("name"): Match(r"^[-_a-zA-Z0-9.]+$"),
                        Optional("wait_for_prompt"): bool,
                        Optional("successes"): [
                            {Required("message"): All(str, Length(min=1))}
                        ],
                        Optional("failures"): [
                            {
                                Required("message"): All(str, Length(min=1)),
                                Optional("exception"): Any(
                                    "InfrastructureError", "JobError", "TestError"
                                ),
                                Optional("error"): All(str, Length(min=1)),
                            }
                        ],
                    }
                ],
            }
        ]
    }
    return {**test.schema(), **base}
