#
# Copyright (C) 2021 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import json
import logging
import socket

SOCKET = "/run/lava-dispatcher-host.sock"

logger = logging.getLogger()


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
