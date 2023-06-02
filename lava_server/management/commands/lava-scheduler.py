# Copyright (C) 2020-present Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import contextlib
import datetime
import signal
import time
from json import JSONDecodeError
from json import loads as json_loads

import zmq
from django.conf import settings
from django.db import connection, transaction
from django.db.utils import InterfaceError, OperationalError
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

        return [
            w.hostname
            for w in Worker.objects.filter(
                state=Worker.STATE_ONLINE, health=Worker.HEALTH_ACTIVE
            )
        ]

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
        self.sub.setsockopt(zmq.SUBSCRIBE, settings.EVENT_TOPIC.encode())
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

    def get_available_dts(self) -> set[str]:
        device_types: set[str] = set()
        with contextlib.suppress(KeyError, zmq.ZMQError):
            while True:
                msg_part_list = self.sub.recv_multipart(zmq.NOBLOCK, copy=True)
                try:
                    topic = msg_part_list[0].decode("utf-8")
                    if not (topic.endswith(".testjob") or topic.endswith(".device")):
                        continue

                    data = json_loads(msg_part_list[4])
                except UnicodeDecodeError:
                    self.logger.error("Invalid event: can't be decoded")
                    continue
                except (IndexError, JSONDecodeError):
                    self.logger.error(f"Invalid event: {msg_part_list}")
                    continue

                if topic.endswith(".testjob"):
                    if data["state"] == "Submitted":
                        device_types.add(data["device_type"])
                elif topic.endswith(".device"):
                    if data["state"] == "Idle" and data["health"] in (
                        "Good",
                        "Unknown",
                        "Looping",
                    ):
                        device_types.add(data["device_type"])

        return device_types

    def main_loop(self) -> None:
        dts: set[str] = set()
        while True:
            begin = time.monotonic()
            try:
                # Check remote worker connectivity
                with transaction.atomic():
                    workers = self.check_workers()

                # Schedule jobs
                schedule(self.logger, dts, workers)
                dts = set()

                # Wait for events
                while not dts and (time.monotonic() - begin) < INTERVAL:
                    timeout = max(INTERVAL - (time.monotonic() - begin), 0)
                    with contextlib.suppress(zmq.ZMQError):
                        self.poller.poll(max(timeout * 1000, 1))
                    dts = self.get_available_dts()

            except (OperationalError, InterfaceError):
                self.logger.info("[RESET] database connection reset.")
                # Closing the database connection will force Django to reopen
                # the connection
                connection.close()
                time.sleep(2)
