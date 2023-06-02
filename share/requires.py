#!/usr/bin/env python3
#
#  requires.py
#
#  Copyright 2018-2019 Linaro Limited
#  Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

import argparse
import os
import sys

import yaml

#  Goals:
#  0: Convert a packaged list of dependencies and versions
#     to a distro-specific list of dependencies.
#  1: Remove need for requirements.txt using Pip syntax as this is
#     misleading.
#  2: output a list of binary package names for the requested distribution
#     and suite to pass to docker scripts and LXC unit test jobs.


def debian(args, depends):
    """
    Special knowledge about how the dependencies work
    for this specific distribution.

    For package building, recurse from backports into
    the parent suite.
    For package names (e.g. docker), require TWO separate
    calls, 1 for backports and one for the parent.
    """
    if args.unittests:
        unittests = set({})
        if args.names and depends[args.package]:
            for key, item in depends[args.package].items():
                if depends[args.package][key].get("unittests"):
                    unittests.add(item["name"])
            if unittests:
                print(" ".join(sorted(unittests)))
        return 0
    if args.names:
        msg = set({})
        backports = set({})
        if not depends.get(args.package):
            return 0
        for key, item in depends[args.package].items():
            if depends[args.package][key].get("unittests"):
                continue
            if args.suite.endswith("-backports"):
                backports.add(item["name"])
                continue
            msg.add(item["name"])
        if backports:
            print(" ".join(sorted(backports)))
        elif msg:
            print(" ".join(sorted(msg)))
        return 0
    if not depends[args.package]:
        return 0
    for item in depends[args.package].keys():
        if depends[args.package][item].get("unittests"):
            continue
        print("%s%s" % (item, depends[args.package][item].get("version", "")))


def load_depends(args, parent):
    req = os.path.join(
        os.path.dirname(__file__), "requirements", args.distribution, "%s.yaml" % parent
    )
    if not os.path.exists(req):
        msg = "Unsupported suite|distribution: %s %s\n\n" % (args.distribution, parent)
        sys.stderr.write(msg)
        raise RuntimeError(msg)
    with open(req) as data:
        depends = yaml.safe_load(data)
    if args.package not in depends:
        msg = "Unknown package: %s\n\n" % args.package
        sys.stderr.write(msg)
        raise RuntimeError(msg)
    return depends


def main():
    """
    Parse options and load requirements files.
    By default, outputs the same list as requirements.txt without
    packages needed for unit tests.
    Use the -n option to only get the distro|suite package names.
    Use the -u option to get the extra packages needed for unit tests.
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
        "-n", "--names", action="store_true", help="List the distribution package names"
    )
    parser.add_argument(
        "-u",
        "--unittests",
        action="store_true",
        help="Distribution package names for unittest support - requires --names",
    )
    args = parser.parse_args()
    args.suite = args.suite.replace("-backports", "")
    args.suite = args.suite.replace("-security", "")
    if args.unittests and not args.names:
        raise RuntimeError("--unittests option requires --names")
    try:
        depends = load_depends(args, args.suite)
    except RuntimeError:
        return 1
    if args.distribution == "debian":
        debian(args, depends)
        if args.suite.endswith("-backports") and not args.names:
            parent = args.suite.replace("-backports", "")
            try:
                ret = load_depends(args, parent)
            except RuntimeError:
                return 2
            debian(args, ret)
    return 0


if __name__ == "__main__":
    sys.exit(main())
