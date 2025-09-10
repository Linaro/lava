#
# Copyright (C) 2020-present Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import argparse
import re
import socket
from dataclasses import dataclass
from pathlib import Path

import sentry_sdk

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


@dataclass
class LavaWorkerBaseOptions:
    name: str
    worker_dir: Path
    ws_url: str | None
    http_timeout: int
    ping_interval: int
    job_log_interval: int
    username: str | None
    token: str
    token_file: Path | None
    log_file: str
    level: str
    sentry_dsn: str | None


def get_base_parser(
    description: str, log_file: str, worker_dir: Path
) -> tuple[argparse.ArgumentParser, argparse._ArgumentGroup, argparse._ArgumentGroup]:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--name", type=str, default=get_fqdn(), help="Name of the worker"
    )
    storage_group = parser.add_argument_group("storage")
    storage_group.add_argument(
        "--worker-dir", type=Path, default=worker_dir, help="Path to data storage"
    )

    net_group = parser.add_argument_group("network")
    net_group.add_argument("--ws-url", default=None, help="WebSocket URL")
    net_group.add_argument(
        "--http-timeout",
        type=int,
        default=10 * 60,
        help="HTTP timeout when requesting the server. Should always be longer than the gunicorn timeout.",
    )
    net_group.add_argument(
        "--ping-interval",
        type=int,
        default=20,
        help="Time between two ping to the server",
    )
    net_group.add_argument(
        "--job-log-interval",
        type=int,
        default=5,
        help="Time between two job log submissions to the server",
    )

    token = parser.add_mutually_exclusive_group()
    token.add_argument(
        "--username", default=None, help="Username for auto registration"
    )
    token.add_argument("--token", default="", help="Worker token")
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

    return parser, storage_group, net_group


def init_sentry_sdk(dsn: str) -> None:
    sentry_sdk.init(dsn=dsn, release=f"lava@{__version__}", traces_sample_rate=1.0)
