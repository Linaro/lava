# Copyright (C) 2019 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from lava_common.constants import UDEV_RULE_FILENAME

if TYPE_CHECKING:
    from typing import TextIO


def handle_rules_show(options):
    from lava_dispatcher_host.udev import get_udev_rules

    print(get_udev_rules())


def handle_rules_install(options):
    from lava_dispatcher_host.udev import get_udev_rules

    dest = UDEV_RULE_FILENAME
    rules = get_udev_rules()
    if os.path.exists(dest) and rules == open(dest).read():
        return
    with open(dest, "w") as f:
        f.write(rules)
    udev_running = (
        subprocess.call(
            ["udevadm", "control", "--ping"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        == 0
    )
    if udev_running:
        subprocess.check_call(["udevadm", "control", "--reload-rules"])


def handle_devices_share(options):
    if options.remote:
        from lava_dispatcher_host.client import Client

        client = Client()
        data = vars(options)
        request = {}
        for f in [
            "device",
            "serial_number",
            "usb_vendor_id",
            "usb_product_id",
            "fs_label",
        ]:
            if f in data:
                request[f] = data[f]
        client.send_request(request)
    else:
        from lava_dispatcher_host.utils import share_device_with_container

        share_device_with_container(options)


def handle_devices_map(options):
    from lava_common.device_mappings import add_device_container_mapping

    container = options.container
    container_type = options.container_type
    job_id = "0"  # fake map
    fields = ["serial_number", "usb_vendor_id", "usb_product_id", "fs_label"]
    device_info = {
        k: options.__dict__[k] for k in fields if k in options and options.__dict__[k]
    }
    add_device_container_mapping(job_id, device_info, container, container_type)


def handle_devices_unmap(_):
    from lava_common.device_mappings import remove_device_container_mappings

    remove_device_container_mappings("0")


def main(argv):
    parser = argparse.ArgumentParser(prog=argv[0])
    parser.set_defaults(usage_from=parser)
    parser.set_defaults(func=None)
    parser.add_argument(
        "--debug-log",
        help="Log debugging information to FILE",
        metavar="FILE",
        type=Path,
    )
    sub = parser.add_subparsers(help="Sub commands")

    # "rules" sub-command
    rules = sub.add_parser("rules", help="Manipulate the udev rules file")
    rules.set_defaults(usage_from=rules)
    rules_sub = rules.add_subparsers()

    # "rules show" action
    rules_show = rules_sub.add_parser("show", help="Generate udev rules file")
    rules_show.set_defaults(func=handle_rules_show)

    # "rules install" action
    rules_install = rules_sub.add_parser(
        "install", help="Install udev rules file to /etc/udev/rules.d/ and reload udev"
    )
    rules_install.set_defaults(func=handle_rules_install)

    # "devices" sub-command
    devices = sub.add_parser("devices", help="Manage devices")
    devices.set_defaults(usage_from=devices)
    devices_sub = devices.add_subparsers()

    # "devices share" action
    devices_share = devices_sub.add_parser(
        "share", help="Share a host device with a container"
    )
    devices_share.add_argument("device", help="Device to be shared")

    # "devices map" action
    devices_map = devices_sub.add_parser(
        "map", help="Map a host device to a container (useful for debugging)"
    )
    devices_map.add_argument("container", help="Container name")
    devices_map.add_argument("container_type", help="Container type (docker)")

    # shared options between "devices share" and "devices map"
    for subparser in [devices_share, devices_map]:
        subparser.add_argument(
            "--serial-number",
            help="Serial number of the device to be shared",
            default=None,
        )
        subparser.add_argument(
            "--vendor-id",
            dest="usb_vendor_id",
            help="Vendor ID of the device to be shared",
            default=None,
        )
        subparser.add_argument(
            "--product-id",
            dest="usb_product_id",
            help="Product ID of the device to be shared",
            default=None,
        )
        subparser.add_argument(
            "--fs-label",
            help="Filesystem label of the device to be shared",
            default=None,
        )

    devices_share.add_argument(
        "--remote",
        action="store_true",
        help="Make a remote request",
    )

    devices_share.set_defaults(func=handle_devices_share)
    devices_map.set_defaults(func=handle_devices_map)

    devices_unmap = devices_sub.add_parser(
        "unmap", help='Remove mappings added with "devices map"'
    )
    devices_unmap.set_defaults(func=handle_devices_unmap)

    options = parser.parse_args(argv[1:])

    if options.func:
        debug_log_file: TextIO | None = None
        if options.debug_log:
            debug_log_file = options.debug_log.open(mode="at")
            if not sys.stderr.isatty():
                sys.stderr = debug_log_file
            timestamp = time.strftime("%c", time.gmtime())
            cmd = shlex.join(argv)
            debug_log_file.write(f"{timestamp} Called with: {cmd}\n")

        options.func(options)

        if debug_log_file is not None:
            debug_log_file.close()
    else:
        options.usage_from.print_help()

    return 0
