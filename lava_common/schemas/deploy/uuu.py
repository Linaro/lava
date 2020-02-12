# -*- coding: utf-8 -*-
#
# Copyright 2019-2020 NXP
#
# Author: Thomas Mahe <thomas.mahe@nxp.com>
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

from voluptuous import Required, Optional, All, Length, Any, Range

from lava_common.schemas import deploy


def schema():
    base = {
        Required("to"): "uuu",
        Required("images"): All(
            {
                Required("boot"): deploy.url(),
                Any(str): {
                    **deploy.url(),
                    Optional("apply-overlay"): bool,
                    Optional("root_partition"): Range(min=0),
                },
            },
            Length(min=1),
        ),
    }
    return {**deploy.schema(), **base}
