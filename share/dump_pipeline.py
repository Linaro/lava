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

import yaml
from jinja2 import FileSystemLoader
from jinja2.sandbox import SandboxedEnvironment as JinjaSandboxEnv

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
    env = JinjaSandboxEnv(autoescape=False, loader=FileSystemLoader(options.path))
    # Load the device configuration
    data = env.from_string(options.device.read()).render()
    device = NewDevice(yaml.safe_load(data))

    # Load the job definition
    parser = JobParser()
    job = parser.parse(options.job.read(), device, 0, None, None, None)

    print(yaml.dump(job.pipeline.describe()))


if __name__ == "__main__":
    sys.exit(main())
