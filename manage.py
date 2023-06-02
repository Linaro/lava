#!/usr/bin/env python3
# Copyright (C) 2016-2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import argparse
import os
import sys

from django.core.management import execute_from_command_line


def find_sources():
    base_path = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(base_path, "lava_server")):
        sys.path.insert(0, base_path)


def main():
    # Is the script called from an installed packages or from a source install?
    installed = not sys.argv[0].endswith("manage.py")

    # Create the command line parser
    parser = argparse.ArgumentParser()
    manage = parser
    if installed:
        subparser = parser.add_subparsers(dest="subcommand", help="Manage LAVA")
        subparser.required = True
        manage = subparser.add_parser("manage")

    manage.add_argument(
        "command", nargs="...", help="Invoke this Django management command"
    )

    # Parse the command line
    options = parser.parse_args()

    # Choose the right Django settings
    if installed:
        settings = "lava_server.settings.prod"
    else:
        # Add the root dir to the python path
        find_sources()
        settings = "lava_server.settings.dev"
    os.environ["DJANGO_SETTINGS_MODULE"] = settings

    # Create and run the Django command line
    execute_from_command_line([sys.argv[0]] + options.command)


if __name__ == "__main__":
    main()
