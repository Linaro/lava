# Copyright (C) 2017 Linaro Limited
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
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import argparse
import simplejson
import os
import subprocess  # nosec - internal
import sys


modules = [
    "lava_common",
    "lava_results_app",
    "lava_scheduler_app",
    "lava_server",
    "linaro_django_xmlrpc",
]
services = [
    "lava-coordinator",
    "lava-logs",
    "lava-master",
    "lava-publisher",
    "lava-server-gunicorn",
    "lava-slave",
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
        default="https://git.linaro.org/lava/lava-server.git",
        help="Url to the lava-master git",
    )

    # "off"
    sub.add_parser("off", help="Deactivate the developer mode")

    # Parse the command line
    options = parser.parse_args()

    # Check that we are running this script on a debian machine
    out = subprocess.check_output(
        ["lsb_release", "--id"], stderr=subprocess.STDOUT  # nosec - internal
    ).decode("utf-8")
    if out != "Distributor ID:\tDebian\n":
        print("Not running on a Debian system")
        sys.exit(1)
    # with lava running in DEBUG
    try:
        with open("/etc/lava-server/settings.conf") as f_conf:
            conf = simplejson.loads(f_conf.read())
            if not conf.get("DEBUG"):
                print("lava-server should be running in 'DEBUG' mode")
                sys.exit(1)
    except OSError as exc:
        print("Unable to open lava-server configuration: %s" % str(exc))
        sys.exit(1)
    except ValueError as exc:
        print("Unable to parse lava-server configuration: %s" % str(exc))
        sys.exit(1)

    # Dispatch
    if options.sub_command == "on":
        handle_on(options)
    else:
        handle_off(options)


if __name__ == "__main__":
    main()
