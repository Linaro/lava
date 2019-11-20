#! /usr/bin/python3

"""
This script is to check the combination of the Jinja2 device-type templates
and the instance-specific device dictionary configuration, to ensure that the
device configuration is valid YAML syntax for each device.

"""

# Copyright 2017 Linaro Limited
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

# pylint gets confused: commands have no shebang, but the file is not a module.


import argparse
import jinja2
import jinja2.exceptions
import glob
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="Check device templates")
    parser.add_argument(
        "--device-types",
        required=True,
        type=str,
        help="Path to the directory containing the device-type jinja2 templates.",
    )
    parser.add_argument(
        "--devices",
        required=True,
        type=str,
        help="Path to directory containing the device dictionary files.",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.devices):
        sys.stderr.write("--devices argument must be a directory\n")
        return 1
    if not os.path.isdir(args.device_types):
        sys.stderr.write("--device-types argument must be a directory\n")
        return 1

    errors = False
    devices = sorted(glob.glob("%s/*.jinja2" % args.devices))

    print("Devices:")
    env = jinja2.Environment(  # nosec - YAML, not HTML, no XSS scope.
        loader=jinja2.FileSystemLoader([args.devices, args.device_types]),
        autoescape=False,
    )

    for device in devices:
        device_name = os.path.splitext(os.path.basename(device))[0]

        try:
            template = env.get_template("%s.jinja2" % device_name)
            device_template = template.render()
        except jinja2.exceptions.TemplateNotFound as exc:
            print('* %s (ERROR): "%s" not found' % (device_name, exc))
            errors = True
        except jinja2.exceptions.TemplateRuntimeError as exc:
            print('* %s (ERROR): rendering error "%s"' % (device_name, exc))
            errors = True
        except jinja2.exceptions.TemplateSyntaxError as exc:
            print(
                '* %s (ERROR): invalid syntax "%s" in "%s"'
                % (device_name, exc, exc.filename)
            )
            errors = True
        else:
            print("* %s" % device_name)

    return errors


if __name__ == "__main__":
    sys.exit(main())
