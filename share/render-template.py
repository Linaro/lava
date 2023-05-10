#! /usr/bin/python3

"""
This script is particularly intended for those adding new devices to LAVA
and developing new jinja templates to create the per-device configuration
in the Device Dictionary database table.

In a production system, the devices directory will be stored in
/etc/lava-server/dispatcher-config/devices/<hostname>.jinja2

When developers are working on new support directly from the command line
lava-dispatch or developing new templates, this script can be used to match the
template output with existing templates.

The path used needs to contain both the jinja2 device-type template in a
device-types/ directory *and* the jinja2 device dictionary file for the device
to review in a devices/ directory.

(This script will go into the lava-dev binary package.)

"""

#  Copyright 2014 Linaro Limited
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# pylint gets confused: commands have no shebang, but the file is not a module.


import argparse
import os

import yaml
from jinja2 import FileSystemLoader
from jinja2.sandbox import SandboxedEnvironment


def main():
    parser = argparse.ArgumentParser(description="LAVA Dispatcher template helper")
    parser.add_argument(
        "--device", type=str, required=True, help="Path to the device template file"
    )
    parser.add_argument(
        "--path",
        default="/etc/lava-server/dispatcher-config/",
        type=str,
        help="Path to the device-types template folder",
    )
    args = parser.parse_args()

    env = SandboxedEnvironment(
        loader=FileSystemLoader(
            [
                os.path.join(args.path, "devices"),
                os.path.join(args.path, "device-types"),
            ]
        ),
        trim_blocks=True,
        autoescape=False,
    )
    if not os.path.exists(
        os.path.join(args.path, "devices", "%s.jinja2" % args.device)
    ):
        print("Cannot find %s device configuration file" % args.device)
        return
    template = env.get_template("%s.jinja2" % args.device)
    ctx = {}
    config = template.render(**ctx)

    print("YAML config")
    print("===========")
    print(config)
    print("Parsed config")
    print("=============")
    print(yaml.safe_load(config))


if __name__ == "__main__":
    main()
