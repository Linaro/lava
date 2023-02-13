# Copyright (C) 2017-2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import argparse
import os
import subprocess  # nosec - internal
import sys

modules = [
    "lava_common",
    "lava_rest_app",
    "lava_results_app",
    "lava_scheduler_app",
    "lava_server",
    "linaro_django_xmlrpc",
]
services = [
    "lava-coordinator",
    "lava-publisher",
    "lava-scheduler",
    "lava-server-gunicorn",
    "lava-worker",
]


def handle_on(options):
    print("Activate the developer mode")
    sources_dir = os.getcwd()

    # Check that the sources are already present
    if not os.path.exists("lava-server/.git"):
        print("Downloading the sources")
        subprocess.check_call(["git", "clone", options.url])  # nosec - internal

    os.chdir("/usr/lib/python3/dist-packages")
    # Making backups
    print("Making backups for:")
    for module in modules:
        if os.path.islink(module):
            print("* %s [SKIP]" % module)
        else:
            print("* %s" % module)
            os.rename(module, module + ".bak")

    # Creating the symlinks
    print("Making symlinks for:")
    for module in modules:
        if os.path.islink(module):
            print("* %s [SKIP]" % module)
        else:
            print("* %s" % module)
            os.symlink(os.path.join(sources_dir, "lava-server", module), module)

    # Restart the services
    _restart()


def handle_off(_):
    print("Deactivate the developer mode")

    os.chdir("/usr/lib/python3/dist-packages")

    # Removing the symlinks
    print("Removing symlinks for:")
    for module in modules:
        if os.path.islink(module):
            print("* %s" % module)
            os.unlink(module)
        else:
            print("* %s [SKIP]" % module)

    # Move back the directories
    print("Restoring backups for:")
    for module in modules:
        if os.path.exists(module + ".bak"):
            print("* %s" % module)
            os.rename(module + ".bak", module)
        else:
            print("* %s [SKIP]" % module)

    # Restart the services
    _restart()


def _restart():
    # Restarting the services
    print("Restarting the services:")
    for service in services:
        print("* %s" % service)
        subprocess.check_call(["service", service, "restart"])  # nosec - internal


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="sub_command", help="Sub commands")
    sub.required = True

    # "on"
    on_parser = sub.add_parser("on", help="Activate the developer mode")
    on_parser.add_argument(
        "--url",
        default="https://git.lavasoftware.org/lava/lava.git",
        help="Url to the lava-master git",
    )

    # "off"
    sub.add_parser("off", help="Deactivate the developer mode")

    # Parse the command line
    options = parser.parse_args()

    # Check that we are running this script on a debian machine
    out = subprocess.check_output(  # nosec - internal
        ["lsb_release", "--id"], stderr=subprocess.STDOUT
    ).decode("utf-8")
    if out != "Distributor ID:\tDebian\n":
        print("Not running on a Debian system")
        sys.exit(1)

    # Dispatch
    if options.sub_command == "on":
        handle_on(options)
    else:
        handle_off(options)


if __name__ == "__main__":
    main()
