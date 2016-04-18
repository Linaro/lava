#! /usr/bin/python

"""
This script is to check the combination of the Jinja2 device-type templates
and the instance-specific device dictionary configuration, to ensure that the
device configuration is valid for each pipeline device on a specified instance.

(This script is part of the lava-dev binary package.)

"""

# Copyright 2016 Linaro Limited
# Author: Neil Williams <neil.williams@linaro.org>
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

# pylint gets confused: commands have no shebang, but the file is not a module.
# pylint: disable=invalid-name


import argparse
import sys
if sys.version > '3':
    import xmlrpc.client as xmlrpclib
else:
    import xmlrpclib


def main():
    parser = argparse.ArgumentParser(description='LAVA Dispatcher template helper')
    parser.add_argument(
        '--instance',
        type=str,
        required=True,
        help='Name of the instance to check')
    parser.add_argument(
        '--hostname',
        default=None,
        type=str,
        help='Device to check (all pipeline devices if not used)')
    parser.add_argument(
        '--https',
        action='store_true',
        help='Use https instead of http')
    args = parser.parse_args()

    protocol = 'https' if args.https else 'http'

    connection = xmlrpclib.ServerProxy("%s://%s//RPC2" % (protocol, args.instance))
    if args.hostname:
        print(connection.scheduler.validate_pipeline_devices(args.hostname))
    else:
        print(connection.scheduler.validate_pipeline_devices())

if __name__ == '__main__':
    main()
