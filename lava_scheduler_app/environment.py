# -*- coding: utf-8 -*-
# Copyright (C) 2015-2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA.  If not, see <http://www.gnu.org/licenses/>.
from __future__ import annotations

from contextvars import ContextVar

import jinja2

from lava_server.files import File

devices_jinja_env: ContextVar[jinja2.Environment] = ContextVar("devices_jinja_env")


def devices():
    try:
        return devices_jinja_env.get()
    except LookupError:
        devices_env = jinja2.Environment(
            loader=File("device").loader(),
            autoescape=False,
            trim_blocks=True,
            cache_size=-1,
        )
        devices_jinja_env.set(devices_env)
        return devices_env


device_types_jinja_env: ContextVar[jinja2.Environment] = ContextVar(
    "device_types_jinja_env"
)


def device_types():
    try:
        return device_types_jinja_env.get()
    except LookupError:
        device_types_env = jinja2.Environment(
            loader=File("device-type").loader(),
            autoescape=False,
            trim_blocks=True,
            cache_size=-1,
        )
        device_types_jinja_env.set(device_types_env)
        return device_types_env
