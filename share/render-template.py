#! /usr/bin/python

"""
This script is particularly intended for those adding new devices to LAVA
and developing new jinja templates to create the per-device configuration
in the DeviceDictionary database table.

To view database entries, as the lavaserver user, view the current jinja data for
a specific device:

 lava-server manage device-dictionary --hostname <HOSTNAME> --export

This template can also be turned into a full version of the actual device
configuration:

 lava-server manage device-dictionary --hostname <HOSTNAME> --review

In a production system, the devices directory will not have any files, with
devices being managed in the database. When developers are working on new support
directly from the command line lava-dispatch or developing new templates,
this script can be used to match the template output with existing templates.

The path used needs to contain both the jinja2 device-type template in a
device-types/ directory *and* the jinja2 device dictionary file for the device
to review in a devices/ directory.

If you use the system path of /etc/lava-server/dispatcher-config/, you'll
temporarily need to create / symlink your device dictionary file into the
devices/ directory at that location. This script only looks for device
configuration files called <HOSTNAME>.jinja2 in the devices/ directory
specified by the --path option or system path default.

(This script will go into the lava-dev binary package.)

"""

#  Copyright 2014 Linaro Limited
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

# pylint gets confused: commands have no shebang, but the file is not a module.
# pylint: disable=invalid-name

import os
import yaml
import argparse
from jinja2 import Environment, FileSystemLoader

# pylint: disable=superfluous-parens,maybe-no-member


def main():

    parser = argparse.ArgumentParser(description='LAVA Dispatcher template helper')
    parser.add_argument(
        '--device',
        type=str,
        required=True,
        help='Path to the device template file')
    parser.add_argument(
        '--path',
        default='/etc/lava-server/dispatcher-config/',
        type=str,
        help='Path to the device-types template folder')
    args = parser.parse_args()

    env = Environment(
        loader=FileSystemLoader(
            [os.path.join(args.path, 'devices'),
             os.path.join(args.path, 'device-types')]),
        trim_blocks=True)
    if not os.path.exists(os.path.join(args.path, 'devices', "%s.jinja2" % args.device)):
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
    print(yaml.load(config))


if __name__ == '__main__':
    main()
