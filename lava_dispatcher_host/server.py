# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Linaro Limited
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
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses>.

import asyncio
import json
import logging
import os
import socket
from argparse import Namespace

from lava_dispatcher_host import share_device_with_container

SOCKET = "/run/lava-dispatcher-host.sock"

logger = logging.getLogger()


class Command:
    def __init__(self, **options):
        self.options = Namespace(**options)


class CommandHandler:
    def handle(self, command: Command):
        if command.options.type == "share":
            share_device_with_container(command.options)


class ServerWrapper:
    def __init__(self, socket=SOCKET):
        self.socket = socket

    def exit(self, signal):
        logger.info(f"Exiting due to {signal}")

    async def start(self):
        logger.info(f"Starting")
        loop = asyncio.get_running_loop()

        sd_sockets = os.getenv("LISTEN_FDS")
        if sd_sockets and int(os.getenv("LISTEN_PID")) == os.getpid():
            # systemd socket activation
            if int(sd_sockets) > 1:
                raise RuntimeError("Only one socket is supported")
            fd = int(os.getenv("SD_LISTEN_FDS_START", "3"))
            sock = socket.fromfd(fd, socket.AF_UNIX, socket.SOCK_STREAM)
            server_kwargs = {"sock": sock}
        else:
            # started directly
            server_kwargs = {"path": self.socket}

        server = await asyncio.start_unix_server(self.handle_request, **server_kwargs)
        async with server:
            await server.serve_forever()

    async def handle_request(self, reader, writer):
        request = await reader.read()
        logger.debug(f"Received request: {request}")

        result = None

        try:
            command = Command(**json.loads(request))
        except (TypeError, json.decoder.JSONDecodeError):
            result = b'{"result": "INVALID_REQUEST"}\n'

        if not result:
            handler = CommandHandler()
            handler.handle(command)
            result = b'{"result": "OK"}\n'

        writer.write(result)
        await writer.drain()
        writer.close()
        await writer.wait_closed()


class Client:
    def __init__(self, socket=SOCKET):
        self.socket = socket

    def send_request(self, request):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(self.socket)
            s.sendall(bytes(json.dumps(request), "utf-8"))
            s.shutdown(socket.SHUT_WR)
            response = s.recv(1024)
            logger.info(str(response))


def main():
    server = ServerWrapper(SOCKET)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        server.exit("SIGINT")


def start():
    if __name__ == "__main__":
        main()


start()
