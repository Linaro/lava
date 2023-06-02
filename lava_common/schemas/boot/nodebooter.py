#
# Copyright (C) 2023 Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
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

from voluptuous import Msg, Optional, Required

from lava_common.schemas import boot


def schema():
    base = {
        Required("method"): Msg("nodebooter", "'method' should be 'nodebooter'"),
        Required("command"): str,
        Optional("prompts"): boot.prompts(),
        Optional("downloads-namespace"): str,
    }
    return {**boot.schema(), **base}
