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

import jinja2
import threading

from lava_server.files import File


def devices():
    thread_locals = threading.local()
    try:
        return thread_locals.devices
    except AttributeError:
        thread_locals.devices = jinja2.Environment(
            loader=File("device").loader(), autoescape=False, trim_blocks=True
        )
    return thread_locals.devices


def device_types():
    thread_locals = threading.local()
    try:
        return thread_locals.device_types
    except AttributeError:
        thread_locals.device_types = jinja2.Environment(
            loader=File("device-type").loader(), autoescape=False, trim_blocks=True
        )
    return thread_locals.device_types
