#! /usr/bin/env python

"""
This script is particularly intended for those adding new devices to LAVA.
Once devices exist, the per-device configuration exists in the database.

The devices directory won't have any files - except when developers are
working on new support directly from the command line lava-dispatch or developing
new templates. (As such, this script will go into the lava-dev binary package once
the playground branch is merged into master.)

"""

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
import sys
import yaml
from jinja2 import Environment, FileSystemLoader

# pylint: disable=superfluous-parens,star-args,maybe-no-member


def main():
    # Check command line
    if len(sys.argv) != 2:
        print("Usage: render-template.py device")
        sys.exit(1)

    device = sys.argv[1]

    env = Environment(
        loader=FileSystemLoader(
            [os.path.join(os.path.dirname(__file__), 'jinja2/devices'),
             os.path.join(os.path.dirname(__file__), 'jinja2/device_types')]),
        trim_blocks=True)
    template = env.get_template("%s.yaml" % device)
    ctx = {}
    config = template.render(**ctx)

    print "YAML config"
    print "==========="
    print config
    print "Parsed config"
    print "============="
    print yaml.load(config)


if __name__ == '__main__':
    main()
