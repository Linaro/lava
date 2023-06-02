#
# Copyright (C) 2019 Linaro Limited
#
# Author: Chase Qi <chase.qi@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from voluptuous import ALLOW_EXTRA, Any, Match, Optional, Required, Schema


def testdef():
    return {
        Required("metadata"): {
            Required("format"): "Lava-Test Test Definition 1.0",
            Required("name"): str,
            Optional("description"): str,
            Optional("environment"): [str],
            Optional("devices"): [str],
            Optional("maintainer"): [str],
            Optional("scope"): [str],
            Optional("os"): [str],
        },
        Optional("install"): {
            Optional("deps"): [str],
            Optional(Match(r"deps-.+")): [str],
            Optional("git-repos"): [str],
            Optional("keys"): [str],
            Optional("steps"): [str],
            Optional("sources"): [str],
        },
        Optional("parameters"): dict,
        Optional("params"): dict,
        Optional("parse"): {
            Optional("fixupdict"): {str: Any("pass", "fail", "skip", "unknown")}
        },
        Optional("run"): {Required("steps"): [str]},
    }


def validate(data):
    schema = Schema(testdef(), extra=ALLOW_EXTRA)
    schema(data)
