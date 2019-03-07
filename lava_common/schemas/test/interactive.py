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

from voluptuous import All, Length, Any, Optional, Required

from lava_common.schemas import test


def schema():
    base = {
        Required("interactive"): [
            {
                Required("name"): str,
                Required("prompts"): [All(str, Length(min=1))],
                Required("script"): [
                    {
                        Required("command"): Any(str, None),
                        Optional("name"): All(str, Length(min=1)),
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
