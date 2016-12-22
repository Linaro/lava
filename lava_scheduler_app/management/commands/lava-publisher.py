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

import fcntl
import grp
import logging
import logging.handlers
import os
import pwd
import signal
import zmq
from zmq.utils.strtypes import b

from django.conf import settings
from django.core.management.base import BaseCommand


FORMAT = "%(asctime)-15s %(levelname)7s %(name)s %(message)s"


class Command(BaseCommand):
    help = "LAVA event publisher"

    def __init__(self, *args, **options):
        super(Command, self).__init__(*args, **options)
        self.logger = logging.getLogger('publisher')

    def add_arguments(self, parser):
        parser.add_argument('-l', '--level',
                            default='DEBUG',
                            help="Logging level (ERROR, WARN, INFO, DEBUG) "
                                 "Default: DEBUG")

        parser.add_argument('-f', '--log-file',
                            default='/var/log/lava-server/lava-publisher.log',
                            help="Logging file path")

        parser.add_argument('-u', '--user',
                            default='lavaserver',
                            help="Run the process under this user. It should "
                                 "be the same user as the gunicorn process.")

        parser.add_argument('-g', '--group',
                            default='lavaserver',
                            help="Run the process under this group. It should "
                                 "be the same group as the gunicorn process.")

    def drop_priviledges(self, user, group):
        try:
            user_id = pwd.getpwnam(user)[2]
            group_id = grp.getgrnam(group)[2]
        except KeyError:
            self.logger.error("Unable to lookup the user or the group")
            return False
        self.logger.debug("Switching to (%s(%d), %s(%d))",
                          user, user_id, group, group_id)

        try:
            os.setgid(group_id)
            os.setuid(user_id)
        except OSError:
            self.logger.error("Unable to the set (user, group)=(%s, %s)",
                              user, group)
            return False

        # Set a restrictive umask (rw-rw-r--)
        os.umask(0o113)

        return True

    def handle(self, *args, **options):
        handler = logging.handlers.WatchedFileHandler(options['log_file'])
        handler.setFormatter(logging.Formatter(FORMAT))
        self.logger.addHandler(handler)

        if options['level'] == 'ERROR':
            self.logger.setLevel(logging.ERROR)
        elif options['level'] == 'WARN':
            self.logger.setLevel(logging.WARN)
        elif options['level'] == 'INFO':
            self.logger.setLevel(logging.INFO)
        else:
            self.logger.setLevel(logging.DEBUG)

        if not settings.EVENT_NOTIFICATION:
            self.logger.error("'EVENT_NOTIFICATION' is set to False, "
                              "LAVA won't generated any events")

        self.logger.info("Dropping priviledges")
        if not self.drop_priviledges(options['user'], options['group']):
            self.logger.error("Unable to drop priviledges")
            return

        self.logger.info("Creating the input socket at %s",
                         settings.INTERNAL_EVENT_SOCKET)
        context = zmq.Context.instance()
        pull = context.socket(zmq.PULL)
        pull.bind(settings.INTERNAL_EVENT_SOCKET)
        poller = zmq.Poller()
        poller.register(pull, zmq.POLLIN)

        # Mask signals and create a pipe that will receive a bit for each
        # signal received. Poll the pipe along with the zmq socket so that we
        # can only be interrupted while reading data.
        (pipe_r, pipe_w) = os.pipe()
        flags = fcntl.fcntl(pipe_w, fcntl.F_GETFL, 0)
        fcntl.fcntl(pipe_w, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        def signal_to_pipe(signum, frame):
            # Send the signal number on the pipe
            os.write(pipe_w, b(chr(signum)))

        signal.signal(signal.SIGHUP, signal_to_pipe)
        signal.signal(signal.SIGINT, signal_to_pipe)
        signal.signal(signal.SIGTERM, signal_to_pipe)
        signal.signal(signal.SIGQUIT, signal_to_pipe)
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
