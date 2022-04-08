# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-present Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses>.

import argparse
import re
import socket
from pathlib import Path


from lava_common.constants import WORKER_DIR


def get_fqdn() -> str:
    """
    Return the fully qualified domain name.
    """
    host = socket.getfqdn()
    if re.match("[-_a-zA-Z0-9.]+$", host):
        return host
    else:
        raise ValueError("Your FQDN contains invalid characters")


def get_parser(docker_worker=False) -> argparse.ArgumentParser:
    if docker_worker:
        description = "LAVA Docker Worker"
        log_file = "/var/log/lava-dispatcher-host/lava-docker-worker.log"
        url_required = False
    else:
        description = "LAVA Worker"
        log_file = "/var/log/lava-dispatcher/lava-worker.log"
        url_required = True

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--name", type=str, default=get_fqdn(), help="Name of the worker"
    )
    if docker_worker:
        parser.add_argument(
            "-d",
            "--devel",
            action="store_true",
            default=False,
            help="Development mode; sets defaults to several options.",
        )
    else:
        parser.add_argument(
            "--debug", action="store_true", default=False, help="Debug lava-run"
        )
        parser.add_argument(
            "--exit-on-version-mismatch",
            action="store_true",
            help="Exit when there is a server mismatch between worker and server.",
        )
        parser.add_argument(
            "--wait-jobs",
            action="store_true",
            help="Wait for jobs to finish prior to exit",
        )

    storage = parser.add_argument_group("storage")
    storage.add_argument(
        "--worker-dir", type=Path, default=WORKER_DIR, help="Path to data storage"
    )
    if docker_worker:
        storage.add_argument(
            "--build-dir",
            type=Path,
            default="/etc/lava-dispatcher-host/build",
            help="Path to a directory with a Dockerfile inside for building customized lava-dispatcher docker image.",
        )

    net = parser.add_argument_group("network")
    net.add_argument("--url", required=url_required, help="Base URL of the server")
    net.add_argument("--ws-url", default=None, help="WebSocket URL")
    net.add_argument(
        "--http-timeout",
        type=int,
        default=10 * 60,
        help="HTTP timeout when requesting the server. Should always be longer than the gunicorn timeout.",
    )
    net.add_argument(
        "--ping-interval",
        type=int,
        default=20,
        help="Time between two ping to the server",
    )
    net.add_argument(
        "--job-log-interval",
        type=int,
        default=5,
        help="Time between two job log submissions to the server",
    )

    token = net.add_mutually_exclusive_group()
    token.add_argument(
        "--username", default=None, help="Username for auto registration"
    )
    token.add_argument("--token", default=None, help="Worker token")
    token.add_argument(
        "--token-file", type=Path, default=None, help="Worker token file"
    )
    log = parser.add_argument_group("logging")
    log.add_argument(
        "--log-file",
        type=str,
        help="Log file for the worker logs",
        default=log_file,
    )
    log.add_argument(
        "--level",
        "-l",
        type=str,
        default="INFO",
        choices=["DEBUG", "ERROR", "INFO", "WARN"],
        help="Log level, default to INFO",
    )

    return parser
