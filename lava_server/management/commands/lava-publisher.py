# Copyright (C) 2016 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
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
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import zmq

from django.conf import settings

from lava_server.cmdutils import LAVADaemonCommand


FORMAT = "%(asctime)-15s %(levelname)7s %(message)s"


class Command(LAVADaemonCommand):
    help = "LAVA event publisher"
    default_logfile = "/var/log/lava-server/lava-publisher.log"

    def handle(self, *args, **options):
        self.setup_logging("publisher", options["level"],
                           options["log_file"], FORMAT)

        self.logger.info("Dropping privileges")
        if not self.drop_privileges(options['user'], options['group']):
            self.logger.error("Unable to drop privileges")
            return

        if not settings.EVENT_NOTIFICATION:
            self.logger.error("'EVENT_NOTIFICATION' is set to False, "
                              "LAVA won't generated any events")

        self.logger.info("Creating the input socket at %s",
                         settings.INTERNAL_EVENT_SOCKET)
        context = zmq.Context.instance()
        pull = context.socket(zmq.PULL)
        pull.bind(settings.INTERNAL_EVENT_SOCKET)
        poller = zmq.Poller()
        poller.register(pull, zmq.POLLIN)

        # Translate signals into zmq messages
        (pipe_r, _) = self.setup_zmq_signal_handler()
        poller.register(pipe_r, zmq.POLLIN)

        # Create the default publishing socket
        self.logger.info("Creating the publication socket at %s",
                         settings.EVENT_SOCKET)
        pub = context.socket(zmq.PUB)
        pub.bind(settings.EVENT_SOCKET)
        # Create the additional PUSH sockets
        self.logger.info("Creating the additional sockets:")
        additional_sockets = []
        for url in settings.EVENT_ADDITIONAL_SOCKETS:
            self.logger.info(" * %s", url)
            sock = context.socket(zmq.PUSH)
            # Allow zmq to keep 10000 pending messages in each queue
            sock.setsockopt(zmq.SNDHWM, 10000)
            sock.connect(url)
            additional_sockets.append(sock)

        self.logger.info("Starting the proxy")
        while True:
            try:
                sockets = dict(poller.poll(None))
            except zmq.error.ZMQError as exc:
                self.logger.error("Received a ZMQ error: %s", exc)
                continue

            if sockets.get(pipe_r) == zmq.POLLIN:
                self.logger.info("Received a signal, leaving")
                break

            if sockets.get(pull) == zmq.POLLIN:
                msg = pull.recv_multipart()
                self.logger.debug("Forwarding: %s", msg)
                pub.send_multipart(msg)
                for (i, sock) in enumerate(additional_sockets):
                    # Send in non blocking mode and print an error message if
                    # the HWM is reached (because the receiver does not grab
                    # the messages fast enough).
                    try:
                        sock.send_multipart(msg, flags=zmq.DONTWAIT)
                    except zmq.error.Again:
                        self.logger.warning("Fail to forward to socket %d", i)
