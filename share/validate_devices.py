#! /usr/bin/python3

"""
This script is to check the combination of the Jinja2 device-type templates
and the instance-specific device dictionary configuration, to ensure that the
device configuration is valid for each pipeline device on a specified instance.

(This script is part of the lava-dev binary package.)

"""

# Copyright 2016 Linaro Limited
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# pylint gets confused: commands have no shebang, but the file is not a module.


import argparse
import xmlrpc.client


def main():
    parser = argparse.ArgumentParser(description="LAVA Dispatcher template helper")
    parser.add_argument(
        "--instance", type=str, required=True, help="Name of the instance to check"
    )
    parser.add_argument(
        "--hostname",
        default=None,
        type=str,
        help="Device to check (all pipeline devices if not used)",
    )
    parser.add_argument(
        "--https", action="store_true", help="Use https instead of http"
    )
    args = parser.parse_args()

    protocol = "https" if args.https else "http"

    connection = xmlrpc.client.ServerProxy("%s://%s//RPC2" % (protocol, args.instance))
    if args.hostname:
        print(connection.scheduler.validate_pipeline_devices(args.hostname))
    else:
        print(connection.scheduler.validate_pipeline_devices())


if __name__ == "__main__":
    main()
