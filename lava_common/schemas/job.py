# -*- coding: utf-8 -*-
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

from voluptuous import All, Any, Length, Optional, Range, Required

from lava_common.schemas import timeout


def schema():
    return {
        Required("job_name"): All(str, Length(min=1, max=200)),
        Required("device_type"): All(str, Length(min=1, max=200)),
        Required("timeouts"): {
            Required("job"): timeout(),
            Optional("action"): timeout(),
            Optional("actions"): {str: timeout()},
            Optional("connection"): timeout(),
            Optional("connections"): {str: timeout()},
        },
        Optional("context"): dict,
        Optional("metadata"): All({Any(int, str): Any(int, str)}),
        Optional("priority"): Any("high", "medium", "low", Range(min=0, max=100)),
        Optional("tags"): [str],
        Optional("secrets"): dict,
        Optional("visibility"): Any("public", "personal", {"group": [str]}),
        Optional("protocols"): dict,  # TODO: validate
        Required("actions"): [{Any("boot", "command", "deploy", "test"): dict}],
    }
