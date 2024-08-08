#!/usr/bin/env python3
#
#  javascript.py
#
#  Copyright 2015 Neil Williams <codehelp@debian.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import os
import sys

import yaml

# Adds a dependency on python-yaml when used during a build.


def check_os(os_name, data):
    """
    Isolate just the data for the requested OS
    Only debian supported so far.
    """
    for key, list_data in data.items():
        if key == os_name:
            yield list_data


def handle_embedded(os_name, data, dirname, simulate=False):
    """
    Remove the packaged duplicate
    Create a symlink from the external package to the old name
    $(RM) $(CURDIR)/$(JS_DIR)/lava_server/static/lava_server/js/jquery-3.6.1.js
    """
    python_dir = None
    dependencies = {}
    os_check = check_os(os_name, data)
    for os_data in next(os_check):
        for dkey, value in os_data.items():
            if dkey == "python_dir":
                python_dir = value
                if python_dir.startswith("/"):
                    python_dir = str(python_dir[1:])
            elif dkey == "package":
                package = os_data
                print(
                    'Linking files from "%s" into "%s"'
                    % (package["package"], package["lava_directory"])
                )
                if "version" in package:
                    dependencies[package["package"]] = "(>= %s)" % package["version"]
                else:
                    dependencies[package["package"]] = None
            elif dkey == "replacements":
                package = os_data
                for ours, external in package["replacements"].items():
                    ext_path = os.path.join(package["directory"], external)
                    our_path = os.path.join(
                        dirname, python_dir, package["lava_directory"], ours
                    )
                    if not os.path.exists(ext_path):
                        print("skipping symlink for %s" % ext_path)
                        continue
                    if not simulate:
                        if not os.path.exists(our_path):
                            raise RuntimeError("missing %s" % our_path)
                        os.unlink(our_path)
                        os.symlink(ext_path, our_path)
                    else:
                        print("rm %s" % our_path)
                        print("ln -s %s %s" % (ext_path, our_path))
    return dependencies


def main():
    """
    Parse options and load the supporting YAML file.
    Where debian is used, debian === debian-based
    """
    parser = argparse.ArgumentParser(description="Handle embedded javascript")
    parser.add_argument(
        "-f",
        "--filename",
        required=True,
        help="YAML file describing embedded javascript",
    )
    parser.add_argument(
        "-r", "--remove", action="store_true", help="Remove original js files from .deb"
    )
    parser.add_argument(
        "-s", "--simulate", action="store_true", help="Only echo the commands"
    )

    args = parser.parse_args()
    data = yaml.safe_load(open(args.filename))
    # only have data for debian-based packages so far.
    dependencies = handle_embedded("debian", data, os.getcwd(), args.simulate)
    dep_list = []
    for package, constraint in dependencies.items():
        if constraint:
            dep_list.append("%s %s" % (package, constraint))
        else:
            dep_list.append(package)
    if args.simulate:
        # only useful for Debian-based
        print("")
        print("Build-Depends:", ", ".join(sorted(dep_list)))
        print("Depends:", ", ".join(sorted(dep_list)))

    return 0


if __name__ == "__main__":
    sys.exit(main())
