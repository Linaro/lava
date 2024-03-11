#
# Copyright (C) 2021 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import asyncio
import json
import logging
import os
import socket
from argparse import Namespace

from lava_dispatcher_host import share_device_with_container

SOCKET = "/run/lava-dispatcher-host.sock"

logger = logging.getLogger()


class ShareCommand:
    def __init__(self, **options):
        self.options = Namespace(**options)


class CommandHandler:
    def handle(self, command: ShareCommand):
        share_device_with_container(command.options)


def encode_result(result, exception=None):
    data = {
        "result": result,
    }
    if exception:
        data["message"] = repr(exception)

    return bytes(json.dumps(data), "utf-8") + b"\n"


class ServerWrapper:
    def __init__(self, socket=SOCKET):
        self.socket = socket

    def exit(self, signal):
        logger.info(f"Exiting due to {signal}")

    async def start(self):
        logger.info("Starting")
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
            command = ShareCommand(**json.loads(request))
        except (TypeError, json.decoder.JSONDecodeError) as ex:
            logger.warning(repr(ex))
            result = encode_result("INVALID_REQUEST", ex)

        if not result:
            try:
                handler = CommandHandler()
                handler.handle(command)
                result = encode_result("OK")
            except Exception as ex:
                logger.warning(repr(ex))
                result = encode_result("FAILED", ex)

        try:
            writer.write(result)
            await writer.drain()
            writer.close()
            await writer.wait_closed()
        except ConnectionResetError as ex:
            logger.warning(repr(ex))


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
