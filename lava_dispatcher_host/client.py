#
# Copyright (C) 2021 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import json
import logging
import socket
from typing import TYPE_CHECKING

from lava_dispatcher_host import SOCKET

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from typing import Any


class Client:
    def __init__(self, socket: str = SOCKET):
        self.socket = socket

    def send_request(self, request: Any) -> Any:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            logger.debug("Connecting to %r", self.socket)
            s.connect(self.socket)
            request_data = bytes(json.dumps(request), "utf-8")
            logger.debug("Sending request: %r", request_data)
            s.sendall(request_data)
            logger.debug("Shutting down socket")
            s.shutdown(socket.SHUT_WR)
            chunks = []
            while chunk := s.recv(4096):
                chunks.append(chunk)
            response = b"".join(chunks)
            logger.debug("Received respounse: %r", response)
        try:
            response_data = json.loads(response)
            logger.info("Request sent and response received successfully")
            return response_data
        except json.JSONDecodeError:
            logger.exception("Failed to decode response JSON: %r", response)
            # the server closed the connection without a reply, e.g.
            # it rejected a non-root peer
            return {"result": "NO_RESPONSE"}
