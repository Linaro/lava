#
# Copyright (C) 2020-present Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import argparse
import re
import socket
from pathlib import Path
from typing import NoReturn

import sentry_sdk

from lava_common.constants import DOCKER_WORKER_DIR, WORKER_DIR
from lava_common.version import __version__


def get_fqdn() -> str:
    """
    Return the fully qualified domain name.
    """
    host = socket.getfqdn()
    if re.match("[-_a-zA-Z0-9.]+$", host):
        return host
    else:
        raise ValueError("Your FQDN contains invalid characters")


def parse_mount(s: str) -> tuple:
    # Split at ':' and accept one, two or three parameters
    src, dst, opts, *extra = *s.split(":"), *(None, None)
    if not src or len(extra) > 2:
        raise argparse.ArgumentTypeError(
            "mount should have 1, 2 or 3 parts (separated by ':')"
        )
    return (src, dst, opts)


def get_parser(docker_worker=False) -> argparse.ArgumentParser:
    if docker_worker:
        description = "LAVA Docker Worker"
        log_file = "/var/log/lava-dispatcher-host/lava-docker-worker.log"
        url_required = False
        worker_dir = DOCKER_WORKER_DIR
    else:
        description = "LAVA Worker"
        log_file = "/var/log/lava-dispatcher/lava-worker.log"
        url_required = True
        worker_dir = WORKER_DIR

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
        parser.add_argument(
            "-m",
            "--mount",
            metavar="SRC[:DST]",
            type=parse_mount,
            nargs="*",
            action="extend",
            help="Bind mount SRC from the host (as DST in the container, if given). Can be given multiple times",
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
        "--worker-dir", type=Path, default=worker_dir, help="Path to data storage"
    )
    if docker_worker:
        storage.add_argument(
            "--build-dir",
            type=Path,
            default="/etc/lava-dispatcher-host/build",
            help="Path to a directory with a Dockerfile inside for building customized lava-dispatcher docker image.",
        )
        storage.add_argument(
            "--use-cache",
            action="store_true",
            default=False,
            help="Use cache when building custom docker worker image.",
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
    parser.add_argument(
        "--sentry-dsn", type=str, default=None, help="Sentry Data Source Name"
    )

    return parser


def init_sentry_sdk(dsn: str) -> NoReturn:
    sentry_sdk.init(dsn=dsn, release=f"lava@{__version__}", traces_sample_rate=1.0)
