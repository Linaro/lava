# -*- coding: utf-8 -*-
#
# Copyright 2019-2020 NXP
#
# Author: Mahe Thomas <thomas.mahe@nxp.com>
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

from voluptuous import Any, Msg, Optional, Required

from lava_common.schemas import boot


def schema():
    base = {
        Required("method"): Msg("uuu", "'method' should be 'uuu'"),
        Required("commands"): Any(str, [{str: str}]),
        Optional("docker"): {Required("image"): str},
    }
    return {**boot.schema(), **base}
