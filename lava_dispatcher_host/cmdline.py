# Copyright (C) 2019 Linaro Limited
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import logging
import os
import subprocess
import syslog

from lava_common.constants import UDEV_RULE_FILENAME
from lava_common.log import YAMLLogger

from lava_dispatcher_host import share_device_with_container
from lava_dispatcher_host.udev import get_udev_rules


logger = None
LINGER = 10000


def setup_logger(data):
    options = argparse.Namespace(**data)

    # Pipeline always log as YAML so change the base logger.
    # Every calls to logging.getLogger will now return a YAMLLogger
    logging.setLoggerClass(YAMLLogger)

    # The logger can be used by the parser and the Job object in all phases.
    global logger
    logger = logging.getLogger("dispatcher")
    if options.logging_url is not None:
        if options.master_cert and options.slave_cert:
            if not os.path.exists(options.master_cert) or not os.path.exists(
                options.slave_cert
            ):
                syslog.syslog(
                    "[%s] Unable to find certificates for %s"
                    % (options.job_id, options.logging_url)
                )
                return None
        # pylint: disable=no-member
        handler = logger.addZMQHandler(
            options.logging_url,
            options.master_cert,
            options.slave_cert,
            options.job_id,
            options.socks_proxy,
            options.ipv6,
        )
    else:
        syslog.syslog("[%s] Logging to streamhandler" % options.job_id)
        logger.addHandler(logging.StreamHandler())

    return logger


def finish_logger():
    if logger:
        logger.close(linger=LINGER)


def handle_rules_show(options):
    print(get_udev_rules())


def handle_rules_install(options):
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
    share_device_with_container(options, setup_logger)
    finish_logger()


def main(argv):
    parser = argparse.ArgumentParser(prog=argv[0])
    sub = parser.add_subparsers(help="Sub commands")

    # "rules" sub-command
    rules = sub.add_parser("rules", help="Manipulate the udev rules file")
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
    devices_sub = devices.add_subparsers()

    # "devices share" action
    devices_share = devices_sub.add_parser(
        "share", help="Share a host device with a container"
    )
    devices_share.add_argument("device", help="Device to be shared")
    devices_share.add_argument(
        "--serial-number", help="Serial number of the device to be shared", default=None
    )
    devices_share.add_argument(
        "--vendor-id", help="Vendor ID of the device to be shared", default=None
    )
    devices_share.add_argument(
        "--product-id", help="Product ID of the device to be shared", default=None
    )
    devices_share.add_argument(
        "--fs-label", help="Filesystem label of the device to be shared", default=None
    )
    devices_share.set_defaults(func=handle_devices_share)

    options = parser.parse_args(argv[1:])
    options.func(options)

    return 0
