#!/usr/bin/python3
#
# Copyright (C) 2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import argparse
import pathlib
import sys

import voluptuous as v
import yaml
from jinja2 import FileSystemLoader
from jinja2.exceptions import TemplateError as JinjaTemplateError
from jinja2.exceptions import TemplateNotFound as JinjaTemplateNotFound
from jinja2.exceptions import TemplateSyntaxError as JinjaTemplateSyntaxError
from jinja2.sandbox import SandboxedEnvironment as JinjaSandboxEnv

from lava_common.schemas import validate as validate_job
from lava_common.schemas.device import validate as validate_device


def check_device(data, options, prefix=""):
    try:
        if options.render:
            data = options.env.from_string(data).render()
        data = yaml.safe_load(data)
    except JinjaTemplateNotFound as exc:
        print("%sinvalide device template:" % prefix)
        print("%smissing template: %s" % (prefix, exc))
        return 1
    except JinjaTemplateSyntaxError as exc:
        print("%sinvalide device template:" % prefix)
        print("%serror: %s" % (prefix, exc))
        print("%sline: %d" % (prefix, exc.lineno))
        return 1
    except JinjaTemplateError as exc:
        print("%sinvalide device template:" % prefix)
        print("%serror: %s" % (prefix, exc))
        print("%serror at: %d" % (prefix, exc.lineno))
        return 1
    except yaml.YAMLError as exc:
        print("%sinvalid device definition:" % prefix)
        print("%sinvalid yaml" % prefix)
        return 1
    try:
        validate_device(data)
    except v.Invalid as exc:
        print("%sinvalid device definition:" % prefix)
        print("%skey: %s" % (prefix, exc.path))
        print("%smgs: %s" % (prefix, exc.msg))
        return 1
    return 0


def check_job(data, options, prefix=""):
    try:
        data = yaml.safe_load(data)
    except yaml.YAMLError as exc:
        print("%sinvalid job definition:" % prefix)
        print("%sinvalid yaml" % prefix)
        return 1
    try:
        validate_job(data, options.strict, options.context)
    except v.Invalid as exc:
        print("%sinvalid job definition:" % prefix)
        print("%skey: %s" % (prefix, exc.path))
        print("%smgs: %s" % (prefix, exc.msg))
        return 1
    return 0


def handle(options, files, glob, check):
    failed = 0
    for fileobj in sorted(files):
        if fileobj.is_dir() and options.recursive:
            files_iter = fileobj.rglob(glob)
        else:
            files_iter = [fileobj]
        for f in sorted(files_iter):
            if not f.exists():
                print("* %s [does not exists]" % str(f))
                failed += 1
                continue
            if not f.as_posix() == "-" and not f.is_file():
                continue
            if f.name in options.exclude:
                print("* %s [skip]" % str(f))
                continue
            if f.as_posix() == "-":
                print("* stdin")
                data = sys.stdin.read()
            else:
                print("* %s" % str(f))
                data = f.read_text(encoding="utf-8")
            if check(data, options, prefix="  -> "):
                failed += 1

    return failed


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="sub_command")
    sub.required = True

    # "job"
    job_parser = sub.add_parser("job", help="check job schema")

    job_parser.add_argument("jobs", type=pathlib.Path, nargs="+", help="job definition")
    job_parser.add_argument(
        "--exclude", type=str, default=[], action="append", help="exclude some jobs"
    )
    job_parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        default=False,
        help="recurse on directories",
    )
    job_parser.add_argument(
        "--strict", action="store_true", default=False, help="make the validator strict"
    )
    job_parser.add_argument(
        "--context",
        action="append",
        default=[],
        type=str,
        help="extra context variables",
    )

    # "device"
    device_parser = sub.add_parser("device", help="check device schema")
    device_parser.add_argument(
        "devices", type=pathlib.Path, nargs="+", help="device definition"
    )
    device_parser.add_argument(
        "--exclude", type=str, default=[], action="append", help="exclude some devices"
    )
    device_parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        default=False,
        help="recurse on directories",
    )
    device_parser.add_argument(
        "--path", type=str, action="append", help="templates lookup path"
    )
    device_parser.add_argument(
        "--no-render",
        action="store_false",
        dest="render",
        help="do not render jinja2 template but look for yaml files instead",
    )

    # Parse the command line
    options = parser.parse_args()

    if options.sub_command == "job":
        return handle(options, options.jobs, "*.yaml", check_job)

    elif options.sub_command == "device":
        if options.render:
            # Add default value for --path
            if options.path is None:
                options.path = [
                    "/etc/lava-server/dispatcher-config/device-types",
                    "/usr/share/lava-server/device-types",
                ]
            # create the jinja2 environment once as this is a slow operation
            options.env = JinjaSandboxEnv(  # nosec - used to render yaml
                autoescape=False, loader=FileSystemLoader(options.path)
            )
            glob = "*.jinja2"
        else:
            glob = "*.yaml"
        return handle(options, options.devices, glob, check_device)
    raise NotImplementedError("Unsupported command")


if __name__ == "__main__":
    sys.exit(main())
