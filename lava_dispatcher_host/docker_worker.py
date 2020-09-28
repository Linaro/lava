# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-present Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
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

import os
import pathlib
import re
import socket
import subprocess
import sys
import urllib

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from lava_common.constants import DISPATCHER_DOWNLOAD_DIR
from lava_common.worker import get_parser


def has_image(image):
    try:
        subprocess.check_call(
            ["docker", "image", "inspect", image],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def get_image(image):
    if has_image(image):
        return

    try:
        subprocess.check_call(["docker", "pull", image])
    except subprocess.CalledProcessError:
        sys.exit(1)


def run(version, options):
    if len(version.split(".")) == 4:
        # development
        image = f"hub.lavasoftware.org/lava/lava/amd64/lava-dispatcher:{version}"
    else:
        # released version
        image = "lavasoftware/lava-dispatcher:{version}"

    service = ["docker", "run", "--rm", "--init", "--privileged", "--net=host"]

    mounts = []
    mounts.append((DISPATCHER_DOWNLOAD_DIR, None))
    mounts.append(("/srv/tftp", None))
    worker_dir = options.worker_dir.absolute()
    worker_dir.mkdir(parents=True, exist_ok=True)
    mounts.append((worker_dir, None))
    mounts.append(("/run/udev", None))
    mounts.append(("/dev", None))
    mounts.append(("/var/run/docker.sock", None))
    mounts.append(("/boot", "readonly=true"))
    mounts.append(("/lib/modules", "readonly=true"))
    for path, opts in mounts:
        m = f"--mount=type=bind,source={path},destination={path}"
        if opts:
            m += "," + opts
        service.append(m)

    # TODO handle ctrl-c/SIGINT
    # TODO dev move: provide default values for all options, including
    # TODO           translate localhost -> 172.17.0.1
    # TODO dev move: build and use docker image from local tree

    # set hostname to have a fixed default worker name
    service.append("--hostname=docker-" + socket.getfqdn())

    get_image(image)
    service.append(image)

    try:
        subprocess.check_call(
            service + ["lava-worker", "--exit-on-version-mismatch"] + sys.argv[1:]
        )
    except subprocess.CalledProcessError as failure:
        sys.exit(failure.returncode)
    except KeyboardInterrupt:
        sys.exit(0)


def get_server_version(options):
    server_version_url = re.sub(r"/$", "", options.url) + "/api/v0.2/system/version/"
    retries = Retry(total=6, backoff_factor=1)
    adapter = HTTPAdapter(max_retries=retries)
    http = requests.Session()
    http.mount("http://", adapter)
    http.mount("https://", adapter)
    server_version = http.get(server_version_url).json()
    return server_version["version"]


def main():
    parser = get_parser(url_required=False)
    parser.add_argument(
        "-d",
        "--devel",
        action="store_true",
        default=False,
        help="Development mode; sets defaults to several options.",
    )

    options = parser.parse_args()

    if options.devel:
        options.url = "http://localhost:8000/"
        options.worker_dir = pathlib.Path.cwd() / "tmp" / "worker-docker"
        sys.argv[1:] = [
            "--level=DEBUG",
            "--log-file=-",
            f"--url={options.url}",
            "--ws-url=http://localhost:8001/",
            f"--worker-dir={options.worker_dir}",
        ]
    elif not options.url:
        print("ERROR: --url option not provided", file=sys.stderr)
        sys.exit(1)

    while True:
        server_version = get_server_version(options)
        run(server_version, options)


if __name__ == "__main__":
    main()
