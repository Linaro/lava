#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
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

import argparse
import jinja2
import os
import sys
import yaml

from lava_dispatcher.device import NewDevice
from lava_dispatcher.parser import JobParser


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("device", type=argparse.FileType(), help="Device template")
    parser.add_argument(
        "--path", type=str, action="append", help="Templates lookup path"
    )
    parser.add_argument("job", type=argparse.FileType(), help="Job definition")

    options = parser.parse_args()

    # Set the default path
    if options.path is None:
        options.path = [
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "etc",
                "dispatcher-config",
                "device-types",
            )
        ]

    # Rendre the device template
    env = jinja2.Environment(  # nosec - used to render yaml
        autoescape=False, loader=jinja2.FileSystemLoader(options.path)
    )
    # Load the device configuration
    data = env.from_string(options.device.read()).render()
    device = NewDevice(yaml.safe_load(data))

    # Load the job definition
    parser = JobParser()
    job = parser.parse(options.job.read(), device, 0, None, None, None)

    print(yaml.dump(job.pipeline.describe(False)))


if __name__ == "__main__":
    sys.exit(main())
