#
# Copyright (C) 2021 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import json
import logging
import socket

from lava_dispatcher_host import SOCKET

logger = logging.getLogger()


class Client:
    def __init__(self, socket=SOCKET):
        self.socket = socket

    def send_request(self, request):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(self.socket)
            s.sendall(bytes(json.dumps(request), "utf-8"))
            s.shutdown(socket.SHUT_WR)
            chunks = []
            while chunk := s.recv(4096):
                chunks.append(chunk)
            response = b"".join(chunks)
            logger.info(str(response))
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # the server closed the connection without a reply, e.g.
            # it rejected a non-root peer
            return {"result": "NO_RESPONSE"}
