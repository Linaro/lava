#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2017 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
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

# Adds the device matching the device-node
# to the lxc identified by lxc-name
#
# Usage: lava_lxc_device_add.py <lxc-name> <device-node>

import os
import argparse
import logging
import subprocess  # nosec - internal
import sys
import time
import syslog

from lava_dispatcher.log import YAMLLogger

# Wait 10s maximum to close the socket
LINGER = 10000

# pylint: disable=line-too-long,missing-docstring


def setup_logger(options):
    # Pipeline always log as YAML so change the base logger.
    # Every calls to logging.getLogger will now return a YAMLLogger
    logging.setLoggerClass(YAMLLogger)

    # The logger can be used by the parser and the Job object in all phases.
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
            options.ipv6,
        )
    else:
        syslog.syslog("[%s] Logging to streamhandler" % options.job_id)
        logger.addHandler(logging.StreamHandler())

    return logger


def main():
    # Configure the parser
    parser = argparse.ArgumentParser()

    parser.add_argument("--lxc-name", required=True, help="Name of the lxc container")
    parser.add_argument("--device-node", required=True, help="Path to the device node")

    group = parser.add_argument_group("logging")
    group.add_argument("--job-id", required=True, metavar="ID", help="Job identifier.")
    group.add_argument(
        "--logging-url",
        metavar="URL",
        default=None,
        help="URL of the ZMQ socket to send the logs to the master",
    )
    group.add_argument(
        "--master-cert", default=None, metavar="PATH", help="Master certificate file"
    )
    group.add_argument(
        "--slave-cert", default=None, metavar="PATH", help="Slave certificate file"
    )
    group.add_argument("--ipv6", action="store_true", default=False, help="Enable IPv6")

    # Parse the command line
    options = parser.parse_args()
    lxc_name = options.lxc_name

    # Setup the logger
    logger = setup_logger(options)
    if not logger:
        syslog.syslog("[%s] Unable to setup the logger, exiting." % (options.job_id))
        return 1

    start = time.gmtime()
    uniq_str = "udev_trigger-%s-%02d:%02d:%02d" % (
        lxc_name,
        start.tm_hour,
        start.tm_min,
        start.tm_sec,
    )

    device = "/dev/%s" % options.device_node

    if not os.path.exists(device):
        logger.debug("Skipping node not in /dev/ : %s" % options.device_node)
        syslog.syslog(
            "[%s] Skipping node not in /dev/ : %s"
            % (options.job_id, options.device_node)
        )
        return 0

    lxc_cmd = ["lxc-device", "-n", lxc_name, "add", device]
    try:
        output = subprocess.check_output(
            lxc_cmd, stderr=subprocess.STDOUT
        )  # nosec - internal
        output = output.decode("utf-8", errors="replace")
        logger.debug(output)
        logger.info("[%s] device %s added", uniq_str, device)
        syslog.syslog("[%s] device %s added" % (uniq_str, device))
    except subprocess.CalledProcessError as exc:
        msg = "[%s] failed to add device %s: '%s'" % (uniq_str, device, exc)
        logger.error(msg)
        syslog.syslog(msg)
        syslog.syslog("[%s] Tried: %s" % (options.job_id, " ".join(lxc_cmd)))
        logger.close(linger=LINGER)  # pylint: disable=no-member
        return 2
    except Exception:
        syslog.syslog("[%s] uncaught exception: %s" % (options.job_id, exc))
        logger.close(linger=LINGER)  # pylint: disable=no-member
        return 3

    logger.close(linger=LINGER)  # pylint: disable=no-member
    return 0


if __name__ == "__main__":
    sys.exit(main())
