#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  requires.py
#
#  Copyright 2018 Neil Williams <neil.williams@linaro.org>
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
#

import os
import sys
import yaml
import argparse


"""
Goals:
0: Convert a packaged list of dependencies and versions
   to a distro-specific list of dependencies.
1: Remove need for requirements.txt using Pip syntax as this is
   misleading.
2: output a list of binary package names for the requested distribution
   and suite to pass to docker scripts and LXC unit test jobs.
"""


def main():
    """
    Parse options and load requirements files.
    By default, outputs the same list as requirements.txt but
    with the Pip name replaced by the distro|suite package name.
    Use the -n option to only get the distro|suite package names.
    """
    parser = argparse.ArgumentParser(description="Handle dependency lists")
    parser.add_argument(
        "-p", "--package", required=True, help="Name of the LAVA package."
    )
    parser.add_argument(
        "-d", "--distribution", required=True, help="Only Debian is supported currently"
    )
    parser.add_argument(
        "-s", "--suite", required=True, help="The distribution suite / release"
    )
    parser.add_argument(
        "-i",
        "--inline",
        action="store_true",
        help="Print in a single line separated by whitespace. Requires --names",
    )
    parser.add_argument(
        "-n",
        "--names",
        action="store_true",
        help="Only output distribution package names, not versions",
    )
    args = parser.parse_args()
    req = os.path.join(
        os.path.dirname(__file__),
        "requirements",
        args.distribution,
        "%s.yaml" % args.suite,
    )
    if not os.path.exists(req):
        sys.stderr.write(
            "Unsupported suite|distribution: %s %s\n\n"
            % (args.distribution, args.suite)
        )
        return 1
    with open(req, "r") as data:
        depends = yaml.safe_load(data)
    if args.package not in depends:
        sys.stderr.write("Unknown package: %s\n\n" % args.package)
        return 2
    if args.names:
        msg = []
        for key, item in depends[args.package].items():
            if depends[args.package][key].get("system"):
                if args.inline:
                    msg.insert(0, key)
                else:
                    print(key)
                continue
            if args.inline:
                msg.append(item["name"])
            else:
                print(item["name"])
        if args.inline:
            print(" ".join(msg))
        return 0
    if not depends[args.package]:
        return 0
    for item in depends[args.package].keys():
        if depends[args.package][item].get("system"):
            continue
        print("%s%s" % (item, depends[args.package][item].get("version", "")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
