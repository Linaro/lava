# -*- coding: utf-8 -*-
# Copyright (C) 2020-present Linaro Limited
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

from typing import Set

import contextlib
import datetime
import json
import signal
import time
import zmq
from zmq.utils.strtypes import b, u

from django.conf import settings
from django.db import connection, transaction
from django.db.utils import OperationalError, InterfaceError
from django.utils import timezone

from lava_common.version import __version__
from lava_scheduler_app.models import Worker
from lava_scheduler_app.scheduler import schedule
from lava_server.cmdutils import LAVADaemonCommand

#############
# CONSTANTS #
#############

INTERVAL = 20
PING_TIMEOUT = 3 * INTERVAL

# Log format
FORMAT = "%(asctime)-15s %(levelname)7s %(message)s"


class Command(LAVADaemonCommand):
    logger = None
    help = "LAVA scheduler"
    default_logfile = "/var/log/lava-server/lava-scheduler.log"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        net = parser.add_argument_group("network")
        net.add_argument(
            "--event-url", default="tcp://localhost:5500", help="URL of the publisher"
        )
        net.add_argument(
            "--ipv6",
            default=False,
            action="store_true",
            help="Enable IPv6 for zmq event stream",
        )

    def check_workers(self):
        query = Worker.objects.select_for_update()
        query = query.filter(state=Worker.STATE_ONLINE)
        query = query.filter(
            last_ping__lt=timezone.now() - datetime.timedelta(seconds=PING_TIMEOUT)
        )
        for worker in query:
            self.logger.info("Worker <%s> is now offline", worker.hostname)
            worker.go_state_offline()
            worker.save()

    def handle(self, *args, **options):
        # Initialize logging.
        self.setup_logging(
            "lava-scheduler", options["level"], options["log_file"], FORMAT
        )

        self.logger.info("[INIT] Starting lava-scheduler")
        self.logger.info("[INIT] Version %s", __version__)

        self.logger.info("[INIT] Dropping privileges")
        if not self.drop_privileges(options["user"], options["group"]):
            self.logger.error("[INIT] Unable to drop privileges")
            return

        self.logger.info("[INIT] Connect to event stream")
        self.logger.debug("[INIT] -> %r", options["event_url"])
        self.context = zmq.Context()
        self.sub = self.context.socket(zmq.SUB)
        self.logger.debug("[INIT] -> %r", settings.EVENT_TOPIC)
        self.sub.setsockopt(zmq.SUBSCRIBE, b(settings.EVENT_TOPIC))
        if options["ipv6"]:
            self.logger.info("[INIT] -> enable IPv6")
            self.sub.setsockopt(zmq.IPV6, 1)
        self.sub.connect(options["event_url"])

        # Every signals should raise a KeyboardInterrupt
        def signal_handler(*_):
            raise KeyboardInterrupt

        signal.signal(signal.SIGTERM, signal_handler)

        # Create a poller
        self.poller = zmq.Poller()
        self.poller.register(self.sub, zmq.POLLIN)

        # Main loop
        self.logger.info("[INIT] Starting main loop")
        try:
            self.main_loop()
        except KeyboardInterrupt:
            self.logger.info("Received a signal, leaving")
        except Exception as exc:
            self.logger.error("[CLOSE] Unknown exception raised, leaving!")
            self.logger.exception(exc)
        self.sub.close(linger=0)
        self.context.term()

    def get_available_dts(self) -> Set[str]:
        device_types: Set[str] = set()
        with contextlib.suppress(KeyError, zmq.ZMQError):
            while True:
                msg = self.sub.recv_multipart(zmq.NOBLOCK)
                try:
                    (topic, _, dt, username, data) = (u(m) for m in msg)
                    data = json.loads(data)
                except UnicodeDecodeError:
                    self.logger.error("Invalid event: can't be decoded")
                    continue
                except ValueError:
                    self.logger.error("Invalid event: %s", msg)
                    continue

                if topic.endswith(".testjob"):
                    if data["state"] == "Submitted":
                        device_types.add(data["device_type"])
                elif topic.endswith(".device"):
                    if data["state"] == "Idle" and data["health"] in [
                        "Good",
                        "Unknown",
                        "Looping",
                    ]:
                        device_types.add(data["device_type"])

        return device_types

    def main_loop(self) -> None:
        dts: Set[str] = set()
        while True:
            begin = time.time()
            try:
                # Check remote worker connectivity
                with transaction.atomic():
                    self.check_workers()

                # Schedule jobs
                schedule(self.logger, dts)
                dts = set()

                # Wait for events
                while not dts and (time.time() - begin) < INTERVAL:
                    timeout = max(INTERVAL - (time.time() - begin), 0)
                    with contextlib.suppress(zmq.ZMQError):
                        self.poller.poll(max(timeout * 1000, 1))
                    dts = self.get_available_dts()

            except (OperationalError, InterfaceError):
                self.logger.info("[RESET] database connection reset.")
                # Closing the database connection will force Django to reopen
                # the connection
                connection.close()
                time.sleep(2)
