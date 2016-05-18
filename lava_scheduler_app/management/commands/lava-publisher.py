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

import logging
import zmq

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "LAVA event publisher"

    def __init__(self, *args, **options):
        super(Command, self).__init__(*args, **options)
        self.logger = logging.getLogger('publisher')

    def add_arguments(self, parser):
        parser.add_argument('-l', '--level',
                            default='DEBUG',
                            help="Logging level (ERROR, WARN, INFO, DEBUG) Default: DEBUG")

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

        self.logger.info("Creating the ZMQ proxy")
        context = zmq.Context.instance()
        pull = context.socket(zmq.PULL)
        pull.bind(settings.INTERNAL_EVENT_SOCKET)
        pub = context.socket(zmq.PUB)
        pub.bind(settings.EVENT_SOCKET)

        self.logger.info("Starting the Proxy")
        try:
            zmq.proxy(pull, pub)
        except KeyboardInterrupt:
            self.logger.info("Received Ctrl+C, leaving")
