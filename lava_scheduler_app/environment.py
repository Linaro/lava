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


thread_locals = threading.local()


thread_locals.devices = jinja2.Environment(
    loader=File("device").loader(), autoescape=False, trim_blocks=True
)

thread_locals.device_types = jinja2.Environment(
    loader=File("device-type").loader(), autoescape=False, trim_blocks=True
)


def devices():
    return thread_locals.devices


def device_types():
    return thread_locals.device_types
