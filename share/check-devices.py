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
# SPDX-License-Identifier: GPL-3.0-or-later

# pylint gets confused: commands have no shebang, but the file is not a module.


import argparse
import glob
import os
import sys

from jinja2 import FileSystemLoader
from jinja2.exceptions import TemplateNotFound as JinjaTemplateNotFound
from jinja2.exceptions import TemplateRuntimeError as JinjaTemplateRuntimeError
from jinja2.exceptions import TemplateSyntaxError as JinjaTemplateSyntaxError
from jinja2.sandbox import SandboxedEnvironment as JinjaSandboxEnv


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
    env = JinjaSandboxEnv(
        loader=FileSystemLoader([args.devices, args.device_types]),
        autoescape=False,
    )

    for device in devices:
        device_name = os.path.splitext(os.path.basename(device))[0]

        try:
            template = env.get_template("%s.jinja2" % device_name)
            device_template = template.render()
        except JinjaTemplateNotFound as exc:
            print('* %s (ERROR): "%s" not found' % (device_name, exc))
            errors = True
        except JinjaTemplateRuntimeError as exc:
            print('* %s (ERROR): rendering error "%s"' % (device_name, exc))
            errors = True
        except JinjaTemplateSyntaxError as exc:
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
