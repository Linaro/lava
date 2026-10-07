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
import struct
from argparse import Namespace

from lava_dispatcher_host import SOCKET
from lava_dispatcher_host.utils import share_device_with_container

logger = logging.getLogger()


class ShareCommand:
    def __init__(self, **options):
        self.options = Namespace(**options)


class CommandHandler:
    def handle(self, command: ShareCommand):
        share_device_with_container(command.options)


def encode_result(result, exception=None):
    data = {"result": result}
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

    def _is_root_peer(self, writer):
        """Return True iff the connected peer is uid 0 (root).

        The socket is root-owned (SocketMode=0600) and the only legitimate
        caller is the root udev rule; a non-root peer is rejected. Fails
        closed if the peer credentials cannot be read.
        """
        sock = writer.transport.get_extra_info("socket")
        try:
            cred = sock.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("iii")
            )
            # struct ucred is {pid, uid, gid}
            _pid, uid, _gid = struct.unpack("iii", cred)
        except (OSError, AttributeError):
            # AttributeError: transport has no "socket" (e.g. already closed).
            return False
        return uid == 0

    async def handle_request(self, reader, writer):
        if not self._is_root_peer(writer):
            logger.warning("Rejecting non-root peer on lava-dispatcher-host socket")
            writer.close()
            return

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


def main():
    server = ServerWrapper(SOCKET)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        server.exit("SIGINT")


if __name__ == "__main__":
    main()
