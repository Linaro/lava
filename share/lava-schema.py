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

from lava_common.schemas import validate


def check_job(data, options, prefix=""):
    data = yaml.safe_load(data)
    try:
        validate(data, options.strict)
    except v.Invalid as exc:
        print("%sInvalid job definition:" % prefix)
        print("%skey: %s" % (prefix, exc.path))
        print("%smgs: %s" % (prefix, exc.msg))
        return 1
    return 0


def handle_job(options):
    failed = 0
    for jobfile in options.jobs:
        if jobfile.is_dir() and options.recursive:
            job_iter = jobfile.rglob("*.yaml")
        else:
            job_iter = [jobfile]
        for job in job_iter:
            if not job.as_posix() == "-" and not job.is_file():
                continue
            if job.name in options.exclude:
                print("* %s [skip]" % str(job))
                continue
            if job.as_posix() == "-":
                print("* stdin")
                data = sys.stdin.read()
            else:
                print("* %s" % str(job))
                data = job.read_text(encoding="utf-8")
            if check_job(data, options, prefix="  -> "):
                failed += 1

    return failed


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="sub_command")
    sub.required = True
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

    options = parser.parse_args()

    if options.sub_command == "job":
        return handle_job(options)
    raise NotImplementedError("Unsupported command")


if __name__ == "__main__":
    sys.exit(main())
