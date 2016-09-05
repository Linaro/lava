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

import grp
import logging
import os
import pwd
import threading
import zmq

from django.conf import settings
from django.core.management.base import BaseCommand


class Monitor(threading.Thread):
    def __init__(self, stop):
        super(Monitor, self).__init__()
        self.stop = stop

    def run(self):
        logger = logging.getLogger('publisher')

        context = zmq.Context.instance()
        socket = context.socket(zmq.PULL)
        socket.connect('inproc:///monitor')

        logger.debug("Waiting for messages on the proxy")
        while not self.stop.is_set():
            # TODO: add a timeout
            data = socket.recv_multipart()
            logger.debug(data)


class Command(BaseCommand):
    help = "LAVA event publisher"

    def __init__(self, *args, **options):
        super(Command, self).__init__(*args, **options)
        self.logger = logging.getLogger('publisher')

    def add_arguments(self, parser):
        parser.add_argument('-l', '--level',
                            default='DEBUG',
                            help="Logging level (ERROR, WARN, INFO, DEBUG) Default: DEBUG")

        parser.add_argument('-u', '--user',
                            default='lavaserver',
                            help="Run the process under this user. It should be the same user as the wsgi process.")

        parser.add_argument('-g', '--group',
                            default='lavaserver',
                            help="Run the process under this group. It should be the same group as the wsgi process.")

    def drop_priviledges(self, user, group):
        try:
            user_id = pwd.getpwnam(user)[2]
            group_id = grp.getgrnam(group)[2]
        except KeyError:
            self.logger.error("Unable to lookup the user or the group")
            return False
        self.logger.debug("Switching to (%s(%d), %s(%d))", user, user_id, group, group_id)

        try:
            os.setgid(group_id)
            os.setuid(user_id)
        except OSError:
            self.logger.error("Unable to the set (user, group)=(%s, %s)", user, group)
            return False

        # Set a restrictive umask (rw-rw-r--)
        os.umask(0o113)

        return True

    def handle(self, *args, **options):
        if options['level'] == 'ERROR':
            self.logger.setLevel(logging.ERROR)
        elif options['level'] == 'WARN':
            self.logger.setLevel(logging.WARN)
        elif options['level'] == 'INFO':
            self.logger.setLevel(logging.INFO)
        else:
            self.logger.setLevel(logging.DEBUG)

        if not settings.EVENT_NOTIFICATION:
            self.logger.error("'EVENT_NOTIFICATION' is set to False, LAVA won't generated any events")

        self.logger.info("Dropping priviledges")
        if not self.drop_priviledges(options['user'], options['group']):
            self.logger.error("Unable to drop priviledges")
            return

        self.logger.info("Creating the ZMQ proxy")
        context = zmq.Context.instance()
        pull = context.socket(zmq.PULL)
        pull.bind(settings.INTERNAL_EVENT_SOCKET)
        pub = context.socket(zmq.PUB)
        pub.bind(settings.EVENT_SOCKET)

        # Create the monitoring thread only in DEBUG
        monitor_in = None
        monitor = None
        if options['level'] == 'DEBUG':
            monitor_in = context.socket(zmq.PUSH)
            monitor_in.bind('inproc:///monitor')

            self.logger.debug("Starting the monitor")
            stop_monitor = threading.Event()
            monitor = Monitor(stop_monitor)
            monitor.start()

        self.logger.info("Starting the Proxy")
        try:
            zmq.proxy(pull, pub, monitor_in)
        except KeyboardInterrupt:
            self.logger.info("Received Ctrl+C, leaving")
            if monitor_in is not None:
                # Stop the monitor thread
                stop_monitor.set()
                # and send a message to unlock the socket
                monitor_in.send('Finishing the monitor')
                monitor.join()
