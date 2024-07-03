#!/usr/bin/env python3
#
#  requires.py
#
#  Copyright 2018-2019 Linaro Limited
#  Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
from __future__ import annotations

import os
from argparse import ArgumentParser
from enum import Enum

import yaml

#  Goals:
#  0: Convert a packaged list of dependencies and versions
#     to a distro-specific list of dependencies.
#  1: Remove need for requirements.txt using Pip syntax as this is
#     misleading.
#  2: output a list of binary package names for the requested distribution
#     and suite to pass to docker scripts and LXC unit test jobs.


class NamesEnum(str, Enum):
    SPACE_SEPARATED = "space-separated"
    DEBIAN_SUBSTVARS = "debian-substvars"


def debian(
    dependencies_data,
    package: str,
    distribution: str,
    suite: str,
    names: NamesEnum | None,
    unittests: bool,
) -> None:
    """
    Special knowledge about how the dependencies work
    for this specific distribution.

    For package building, recurse from backports into
    the parent suite.
    For package names (e.g. docker), require TWO separate
    calls, 1 for backports and one for the parent.
    """
    if unittests:
        unittests = set({})

        if names and dependencies_data[package]:
            for key, item in dependencies_data[package].items():
                if dependencies_data[package][key].get("unittests"):
                    unittests.add(item["name"])

            if unittests:
                print(" ".join(sorted(unittests)))
        return

    if names is not None:
        package_names: set[str] = set({})

        if not dependencies_data.get(package):
            return

        for key, item in dependencies_data[package].items():
            if dependencies_data[package][key].get("unittests"):
                continue

            package_names.add(item["name"])

        if names == NamesEnum.SPACE_SEPARATED:
            print(" ".join(sorted(package_names)))
        elif names == NamesEnum.DEBIAN_SUBSTVARS:
            print(f"{package}:Depends=" + ", ".join(sorted(package_names)))
        return

    if not dependencies_data[package]:
        return

    for item in dependencies_data[package].keys():
        if dependencies_data[package][item].get("unittests"):
            continue
        print("%s%s" % (item, dependencies_data[package][item].get("version", "")))


def load_depends(distribution: str, suite: str, package: str) -> None:
    req = os.path.join(
        os.path.dirname(__file__), "requirements", distribution, f"{suite}.yaml"
    )
    if not os.path.exists(req):
        raise RuntimeError(f"Unsupported suite|distribution: {distribution} {suite}")

    with open(req) as data:
        dependencies_data = yaml.safe_load(data)
    if package not in dependencies_data:
        raise RuntimeError(f"Unknown package: {package}")
    return dependencies_data


def main(
    package: str,
    distribution: str,
    suite: str,
    names: NamesEnum | None,
    unittests: bool,
) -> None:
    """
    Parse options and load requirements files.
    By default, outputs the same list as requirements.txt without
    packages needed for unit tests.
    Use the -n option to only get the distro|suite package names.
    Use the -u option to get the extra packages needed for unit tests.
    """
    suite = suite.replace("-backports", "")
    suite = suite.replace("-security", "")
    if unittests and names is None:
        raise RuntimeError("--unittests option requires --names")

    dependencies_data = load_depends(distribution, suite, package)

    if distribution == "debian":
        debian(dependencies_data, package, distribution, suite, names, unittests)
    else:
        raise ValueError("Unknown distribution:", distribution)


if __name__ == "__main__":
    parser = ArgumentParser(description="Handle dependency lists")
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
        "-n",
        "--names",
        nargs="?",
        type=NamesEnum,
        const=NamesEnum.SPACE_SEPARATED,
        choices=[n.value for n in NamesEnum],
        help="List the distribution package names",
    )
    parser.add_argument(
        "-u",
        "--unittests",
        action="store_true",
        help="Distribution package names for unittest support - requires --names",
    )
    main(**vars(parser.parse_args()))
