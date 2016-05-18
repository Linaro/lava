#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

from lava_dispatcher.pipeline.device import NewDevice
from lava_dispatcher.pipeline.parser import JobParser

import optparse
import yaml


if __name__ == '__main__':
    usage = "Usage: %prog device_name job.yaml"
    description = "LAVA dispatcher pipeline helper. Dump the pipeline that " \
                  "was built for the given job on the given device"

    parser = optparse.OptionParser(usage=usage, description=description)
    (options, args) = parser.parse_args()
    if len(args) != 2:
        print("Missing job option, try -h for help")
        exit(1)

    # Create the device
    device = None
    try:
        device = NewDevice(args[0])
    except RuntimeError:
        print("No device configuration found for %s" % args[0])
        exit(1)

    # Load the job definition
    with open(args[1], 'r') as job_data:
        parser = JobParser()
        job = parser.parse(job_data, device, 0, None, None, None)

    print(yaml.dump(job.pipeline.describe(False)))
