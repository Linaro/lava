#
# Copyright (C) 2021 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import struct
from argparse import Namespace
from typing import TYPE_CHECKING

from lava_dispatcher_host import SOCKET
from lava_dispatcher_host.utils import share_device_with_container

if TYPE_CHECKING:
    from asyncio import StreamReader, StreamWriter
    from typing import Any

logger = logging.getLogger(__name__)


class ShareCommand:
    def __init__(self, **options: Any):
        self.options = Namespace(**options)


class CommandHandler:
    def handle(self, command: ShareCommand) -> None:
        logger.debug(
            "Executing share device with container command: %r", command.options
        )
        share_device_with_container(command.options)


def encode_result(result: str, exception: BaseException | None = None) -> bytes:
    data = {"result": result}
    if exception:
        data["message"] = repr(exception)

    return bytes(json.dumps(data), "utf-8") + b"\n"


class ServerWrapper:
    def __init__(self, socket: str = SOCKET):
        self.socket = socket

    def exit(self, signal: str) -> None:
        logger.info("Exiting due to %r signal", signal)

    async def start(self) -> None:
        logger.info("Starting")

        sd_sockets = os.getenv("LISTEN_FDS")
        if sd_sockets and int(os.getenv("LISTEN_PID") or -1) == os.getpid():
            # systemd socket activation
            if int(sd_sockets) > 1:
                raise RuntimeError("Only one socket is supported")
            fd = int(os.getenv("SD_LISTEN_FDS_START", "3"))
            logger.debug("Using systemd.socket")
            sock = socket.fromfd(fd, socket.AF_UNIX, socket.SOCK_STREAM)
            server_kwargs: dict[str, Any] = {"sock": sock}
        else:
            # started directly
            server_kwargs = {"path": self.socket}

        server = await asyncio.start_unix_server(self.handle_request, **server_kwargs)
        async with server:
            await server.serve_forever()

    def _is_root_peer(self, writer: StreamWriter) -> bool:
        """Return True iff the connected peer is uid 0 (root).

        The socket is root-owned (SocketMode=0600) and the only legitimate
        caller is the root udev rule; a non-root peer is rejected. Fails
        closed if the peer credentials cannot be read.
        """
        logger.debug("Checking peer credentials")
        sock = writer.transport.get_extra_info("socket")
        try:
            cred = sock.getsockopt(
                socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("iii")
            )

            # struct ucred is {pid, uid, gid}
            cred_tuple: tuple[int, int, int] = struct.unpack("iii", cred)
            _pid, uid, _gid = cred_tuple
        except (OSError, AttributeError):
            # AttributeError: transport has no "socket" (e.g. already closed).
            return False
        return uid == 0

    async def handle_request(self, reader: StreamReader, writer: StreamWriter) -> None:
        if not self._is_root_peer(writer):
            logger.warning("Rejecting non-root peer on lava-dispatcher-host socket")
            writer.close()
            return

        request = await reader.read()
        logger.debug("Received request: %r", request)

        result = b""

        command: ShareCommand | None = None
        try:
            command = ShareCommand(**json.loads(request))
        except (TypeError, json.decoder.JSONDecodeError) as ex:
            logger.warning(repr(ex))
            result = encode_result("INVALID_REQUEST", ex)

        if not result:
            logger.debug("No request result. Returning 'OK'.")
            if command is None:
                # unreachable unless the branch above stops setting result
                result = encode_result("INVALID_REQUEST")
            else:
                try:
                    handler = CommandHandler()
                    handler.handle(command)
                    result = encode_result("OK")
                except Exception as ex:
                    logger.exception("Failed to execute command: %r", command.options)
                    result = encode_result("FAILED", ex)

        try:
            logger.debug("Sending back result: %r", result)
            writer.write(result)
            await writer.drain()
            writer.close()
            await writer.wait_closed()
        except ConnectionResetError:
            logger.warning("Client disconnected before reading result: %r", result)


def main() -> None:
    server = ServerWrapper(SOCKET)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        server.exit("SIGINT")


if __name__ == "__main__":
    main()
