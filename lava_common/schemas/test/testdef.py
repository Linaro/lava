# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Linaro Limited
#
# Author: Chase Qi <chase.qi@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

from voluptuous import Any, Match, Optional, Required, Schema, ALLOW_EXTRA


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
