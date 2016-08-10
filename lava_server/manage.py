#!/usr/bin/env python
#
# Copyright (C) 2016 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA Server.
#
# LAVA Server is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA Server is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA Server.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import os
import sys

from django.core.management import execute_from_command_line


def find_sources():
    base_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..")
    if os.path.exists(os.path.join(base_path, "lava_server")):
        sys.path.insert(0, base_path)


def main():
    # Is the script called from an installed packages or from a source install?
    installed = not sys.argv[0].endswith('manage.py')

    # Create the command line parser
    parser = argparse.ArgumentParser()
    if installed:
        subparser = parser.add_subparsers(title='subcommand', help='Manage LAVA')
        manage = subparser.add_parser("manage")
    else:
        manage = parser

    group = manage.add_argument_group("Server configuration")

    group.add_argument("-I", "--instance-template",
                       action="store",
                       default="/etc/lava-server/{filename}.conf",
                       help="Template used for constructing instance pathname."
                            " The default value is: %(default)s")

    manage.add_argument("command", nargs="...",
                        help="Invoke this Django management command")

    # Parse the command line
    options = parser.parse_args()

    # Choose the right Django settings
    if installed:
        settings = "lava_server.settings.distro"
    else:
        # Add the root dir to the python path
        find_sources()
        settings = "lava_server.settings.development"
    os.environ["DJANGO_SETTINGS_MODULE"] = settings
    os.environ["DJANGO_DEBIAN_SETTINGS_TEMPLATE"] = options.instance_template

    # Create and run the Django command line
    django_options = [sys.argv[0]]
    django_options.extend(options.command)
    execute_from_command_line(django_options)

if __name__ == "__main__":
    main()
