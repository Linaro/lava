# -*- coding: utf-8 -*-
# Copyright (C) 2015-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA.  If not, see <http://www.gnu.org/licenses/>.

import os
import zmq
from zmq.utils.strtypes import u

from django.conf import settings

from lava_common.version import __version__
from lava_server.cmdutils import LAVADaemonCommand


TIMEOUT = 5
FORMAT = "%(asctime)-15s %(levelname)7s %(message)s"


class Command(LAVADaemonCommand):
    help = "LAVA event publisher"
    default_logfile = "/var/log/lava-server/lava-publisher.log"

    def forward_event(self, leaving):
        try:
            sockets = dict(self.poller.poll(TIMEOUT * 1000 if leaving else None))
        except zmq.error.ZMQError as exc:
            self.logger.error("[POLL] Received a ZMQ error: %s", exc)
            return True

        if sockets.get(self.pipe_r) == zmq.POLLIN:
            # remove the message from the queue
            os.read(self.pipe_r, 1)
            if leaving:
                self.logger.warning(
                    "[POLL] signal already handled, please wait for the process to exit"
                )
                return True
            else:
                self.logger.info("[POLL] received a signal, leaving")
                return False

        if sockets.get(self.pull) == zmq.POLLIN:
            msg = self.pull.recv_multipart()
            self.logger.debug("[POLL] Forwarding: %s", msg)
            self.pub.send_multipart(msg)
            for (i, sock) in enumerate(self.additional_sockets):
                # Send in non blocking mode and print an error message if
                # the HWM is reached (because the receiver does not grab
                # the messages fast enough).
                try:
                    sock.send_multipart(msg, flags=zmq.DONTWAIT)
                except zmq.error.Again:
                    self.logger.warning("[POLL] Fail to forward to socket %d", i)
        return not leaving

    def handle(self, *args, **options):
        self.setup_logging(
            "lava-publisher", options["level"], options["log_file"], FORMAT
        )

        self.logger.info("[INIT] Starting lava-publisher")
        self.logger.info("[INIT] Version %s", __version__)

        self.logger.info("[INIT] Dropping privileges")
        if not self.drop_privileges(options["user"], options["group"]):
            self.logger.error("[INIT] Unable to drop privileges")
            return

        if not settings.EVENT_NOTIFICATION:
            self.logger.error(
                "[INIT] 'EVENT_NOTIFICATION' is set to False, "
                "LAVA won't generated any events"
            )

        self.logger.info(
            "[INIT] Creating the input socket at %s", settings.INTERNAL_EVENT_SOCKET
        )
        context = zmq.Context.instance()
        self.pull = context.socket(zmq.PULL)
        self.pull.bind(settings.INTERNAL_EVENT_SOCKET)
        self.poller = zmq.Poller()
        self.poller.register(self.pull, zmq.POLLIN)

        # Translate signals into zmq messages
        (self.pipe_r, _) = self.setup_zmq_signal_handler()
        self.poller.register(self.pipe_r, zmq.POLLIN)

        # Create the default publishing socket
        self.logger.info(
            "[INIT] Creating the publication socket at %s", settings.EVENT_SOCKET
        )
        self.pub = context.socket(zmq.PUB)
        # Ask zmq to send heart beats
        # See api.zeromq.org/4-2:zmq-setsockopt#toc17
        self.pub.setsockopt(zmq.HEARTBEAT_IVL, 5000)
        self.pub.setsockopt(zmq.HEARTBEAT_TIMEOUT, 15000)
        self.pub.setsockopt(zmq.HEARTBEAT_TTL, 15000)
        # bind
        self.pub.bind(settings.EVENT_SOCKET)
        # Create the additional PUSH sockets
        if settings.EVENT_ADDITIONAL_SOCKETS:
            self.logger.info("[INIT] Creating the additional sockets:")
        self.additional_sockets = []
        for url in settings.EVENT_ADDITIONAL_SOCKETS:
            self.logger.info("[INIT]  * %s", url)
            sock = context.socket(zmq.PUSH)
            # Allow zmq to keep 10000 pending messages in each queue
            sock.setsockopt(zmq.SNDHWM, 10000)
            # Ask zmq to send heart beats
            # See api.zeromq.org/4-2:zmq-setsockopt#toc17
            self.pub.setsockopt(zmq.HEARTBEAT_IVL, 5000)
            self.pub.setsockopt(zmq.HEARTBEAT_TIMEOUT, 15000)
            self.pub.setsockopt(zmq.HEARTBEAT_TTL, 15000)
            # connect
            sock.connect(url)
            self.additional_sockets.append(sock)

        self.logger.info("[INIT] Starting the proxy")
        while self.forward_event(False):
            pass

        # Carefully close the logging socket as we don't want to lose messages
        self.logger.info("[EXIT] Disconnect pull socket and process messages")
        endpoint = u(self.pull.getsockopt(zmq.LAST_ENDPOINT))
        self.logger.debug("[EXIT] unbinding from '%s'", endpoint)
        self.pull.unbind(endpoint)

        while self.forward_event(True):
            pass

        # Close the sockets allowing 1s each to leave
        self.logger.info("[EXIT] Closing the sockets: the queue is empty")
        self.pull.close(linger=1)
        self.pub.close(linger=1)
        for socket in self.additional_sockets:
            socket.close(linger=1)
        context.term()
