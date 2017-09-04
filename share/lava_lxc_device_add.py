#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2017 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Coordinator is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Coordinator is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses>.
#
# Reads content of device-info-file and adds the given devices to lxc
# identified by lxc-name
#
# Usage: lava_lxc_device_add.py <lxc-name> <device-info-file>

import sys
import ast
import subprocess
from lava_dispatcher.pipeline.utils.udev import get_udev_devices


lxc_name = sys.argv[1]
device_info = ast.literal_eval(open(sys.argv[2], 'r').read())
device_paths = get_udev_devices(device_info=device_info)
for device in device_paths:
    lxc_cmd = ['lxc-device', '-n', lxc_name, 'add', device]
    output = subprocess.check_output(lxc_cmd, stderr=subprocess.STDOUT)
    print(output)
    print("%s: device %s added" % (lxc_name, device))
