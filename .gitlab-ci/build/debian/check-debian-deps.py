#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import argparse
import pathlib
import re
import subprocess
import sys
import yaml


def load_requirements(suite, package):
    debian = pathlib.Path("share/requirements/debian")
    requirements = {}
    if suite.endswith("-backports"):
        base_suite = suite.replace("-backports", "")
        data = yaml.safe_load(
            (debian / ("%s.yaml" % base_suite)).read_text(encoding="utf-8")
        )[package]
        if data is not None:
            requirements = data
    data = yaml.safe_load((debian / ("%s.yaml" % suite)).read_text(encoding="utf-8"))[
        package
    ]
    if data is not None:
        requirements.update(data)

    return requirements


def prune_requirements(requirements):
    return {
        v["name"]: v.get("version", "")
        for k, v in requirements.items()
        if not v.get("unittests", False)
    }


def list_dependencies(filename):
    out = subprocess.check_output(
        ["dpkg", "-I", filename], stderr=subprocess.STDOUT
    ).decode("utf-8")
    deps = None
    for line in out.split("\n"):
        if line.startswith(" Depends: "):
            deps = line.replace(" Depends: ", "")
            break

    pattern = re.compile(r"(.+) \(>= (.+)\)$")
    dependencies = {}
    for dep in deps.split(", "):
        m = pattern.match(dep)
        if m is not None:
            dependencies[m.group(1)] = ">=" + m.group(2)
        else:
            dependencies[dep] = ""

    return dependencies


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", required=True, help="debian distributions")
    parser.add_argument(
        "--package",
        required=True,
        choices=["lava-common", "lava-dispatcher", "lava-dispatcher-host", "lava-server"],
        help="debian package",
    )
    parser.add_argument("filename", type=str, help="debian package")

    options = parser.parse_args()

    # Load and prune requirements
    reqs = load_requirements(options.suite, options.package)
    reqs = prune_requirements(reqs)

    # List debian package dependencies
    deps = list_dependencies(options.filename)

    failures = 0
    for req in sorted(reqs):
        if req not in deps:
            ok = False
            ok_str = "MISSING"
        else:
            ok = bool(reqs[req] == deps[req])
            ok_str = "OK" if ok else "NOK"
        failures += not ok
        string_str = " (%s)" % reqs[req] if reqs[req] else ""
        print("* %s%s [%s]" % (req, string_str, ok_str))

    return failures


if __name__ == "__main__":
    sys.exit(main())
