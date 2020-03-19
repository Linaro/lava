# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
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

from voluptuous import Optional, Required

from lava_common.schemas import deploy


postprocess_with_docker = {Required("image"): str, Required("steps"): [str]}


def schema():
    base = {
        Required("to"): "downloads",
        Required("images"): {Required(str, "'images' is empty"): deploy.url()},
        Optional("postprocess"): {Required("docker"): postprocess_with_docker},
    }
    return {**deploy.schema(), **base}
