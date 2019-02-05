# coding: utf-8
#
# Copyright (C) 2018 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
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

from voluptuous import Any, Match, Optional, Required

from lava_common.schemas import test


def schema(live=False):
    common = {
        Required("path"): str,
        Required("name"): str,
        Optional("skip_install"): [
            Any("keys", "sources", "deps", "steps", "git-repos", "all")
        ],
        # Optional("parameters"):
    }

    base = {
        Required("definitions"): [
            Any(
                {
                    Required("repository"): str,
                    Required("from"): Any("git", "bzr"),
                    Optional("branch"): str,
                    Optional("lava-signal"): Any("kmsg", "stdout"),
                    Optional("history"): bool,
                    Optional("revision"): str,
                    Optional("parameters"): {str: Any(str, None)},
                    Optional("params"): {str: Any(str, None)},
                    **common,
                },
                {
                    Required("repository"): {
                        Required("metadata"): dict,  # TODO: what's required?
                        Optional("install"): {
                            Optional("deps"): [str],
                            Optional(Match(r"deps-.+")): [str],
                            Optional("git-repos"): [str],
                            Optional("keys"): [str],
                            Optional("steps"): [str],
                            Optional("sources"): [str],
                        },
                        Optional("run"): {Required("steps"): [str]},
                    },
                    Required("from"): "inline",
                    **common,
                },
            )
        ]
    }
    return {**test.schema(live), **base}
