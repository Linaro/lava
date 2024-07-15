#!/usr/bin/python3
#
# Copyright (C) 2015 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import argparse
import os
import sys

from jinja2 import FileSystemLoader

from lava_common.jinja import create_device_templates_env
from lava_common.yaml import yaml_safe_dump
from lava_dispatcher.device import DeviceDict
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
    env = create_device_templates_env(loader=FileSystemLoader(options.path))
    # Load the device configuration
    data = env.from_string(options.device.read()).render()
    device = DeviceDict.from_yaml_str(data)

    # Load the job definition
    parser = JobParser()
    job = parser.parse(options.job.read(), device, 0, None, None, None)

    sys.stdout.write(yaml_safe_dump(job.pipeline.describe()))


if __name__ == "__main__":
    sys.exit(main())
