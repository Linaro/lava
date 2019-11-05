#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Linaro Limited
#
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
# along with this program; if not, see <http://www.gnu.org/licenses>.

import argparse
import pathlib
import sys
import voluptuous as v
import yaml

from lava_common.schemas import validate as validate_job
from lava_common.schemas.device import validate as validate_device


def check_device(data, options, prefix=""):
    try:
        data = yaml.safe_load(data)
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


def handle(options, files, check):
    failed = 0
    for fileobj in files:
        if fileobj.is_dir() and options.recursive:
            files_iter = fileobj.rglob("*.yaml")
        else:
            files_iter = [fileobj]
        for f in files_iter:
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

    # Parse the command line
    options = parser.parse_args()

    if options.sub_command == "job":
        return handle(options, options.jobs, check_job)
    elif options.sub_command == "device":
        return handle(options, options.devices, check_device)
    raise NotImplementedError("Unsupported command")


if __name__ == "__main__":
    sys.exit(main())
