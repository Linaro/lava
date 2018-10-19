# -*- coding: utf-8 -*-
# Copyright (C) 2017-2018 Linaro Limited
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

# pylint: disable=wrong-import-order,bad-continuation

import contextlib
import logging
import os
import time
import yaml
import zmq
import zmq.auth
from zmq.utils.strtypes import u
from zmq.auth.thread import ThreadAuthenticator
from django.conf import settings
from django.db import connection, transaction
from django.db.utils import DatabaseError, InterfaceError, OperationalError

from lava_results_app.models import TestCase
from lava_server.cmdutils import LAVADaemonCommand, watch_directory
from lava_scheduler_app.models import TestJob
from lava_scheduler_app.signals import send_event
from lava_scheduler_app.utils import mkdir
from lava_scheduler_app.logutils import line_count, write_logs
from lava_results_app.dbutils import map_scanned_results, create_metadata_store


# Constants
FORMAT = "%(asctime)-15s %(levelname)7s %(message)s"
TIMEOUT = 10
BULK_CREATE_TIMEOUT = 10
FD_TIMEOUT = 60


class JobHandler:  # pylint: disable=too-few-public-methods
    def __init__(self, job):
        self.output_dir = job.output_dir
        self.output = open(os.path.join(self.output_dir, "output.yaml"), "ab")
        self.index = open(os.path.join(self.output_dir, "output.idx"), "ab")
        self.last_usage = time.time()
        self.markers = {}

    def write(self, message):
        write_logs(self.output, self.index, (message + "\n").encode("utf-8"))

    def line_count(self):
        return line_count(self.index)

    def close(self):
        self.index.close()
        self.output.close()


class Command(LAVADaemonCommand):
    help = "LAVA log recorder"
    logger = None
    default_logfile = "/var/log/lava-server/lava-logs.log"

    def __init__(self, *args, **options):
        super().__init__(*args, **options)
        self.logger = logging.getLogger("lava-logs")
        self.log_socket = None
        self.auth = None
        self.controler = None
        self.inotify_fd = None
        self.pipe_r = None
        self.poller = None
        self.cert_dir_path = None
        # List of logs
        self.jobs = {}
        # Keep test cases in memory
        self.test_cases = []
        # Master status
        self.last_ping = 0
        self.ping_interval = TIMEOUT

    def add_arguments(self, parser):
        super().add_arguments(parser)

        net = parser.add_argument_group("network")
        net.add_argument(
            "--socket",
            default="tcp://*:5555",
            help="Socket waiting for logs. Default: tcp://*:5555",
        )
        net.add_argument(
            "--master-socket",
            default="tcp://localhost:5556",
            help="Socket for master-slave communication. Default: tcp://localhost:5556",
        )
        net.add_argument(
            "--ipv6",
            default=False,
            action="store_true",
            help="Enable IPv6 on the listening sockets",
        )
        net.add_argument(
            "--encrypt", default=False, action="store_true", help="Encrypt messages"
        )
        net.add_argument(
            "--master-cert",
            default="/etc/lava-dispatcher/certificates.d/master.key_secret",
            help="Certificate for the master socket",
        )
        net.add_argument(
            "--slaves-certs",
            default="/etc/lava-dispatcher/certificates.d",
            help="Directory for slaves certificates",
        )

    def handle(self, *args, **options):
        # Initialize logging.
        self.setup_logging("lava-logs", options["level"], options["log_file"], FORMAT)

        self.logger.info("[INIT] Dropping privileges")
        if not self.drop_privileges(options["user"], options["group"]):
            self.logger.error("[INIT] Unable to drop privileges")
            return

        filename = os.path.join(settings.MEDIA_ROOT, "lava-logs-config.yaml")
        self.logger.debug("[INIT] Dumping config to %s", filename)
        with open(filename, "w") as output:
            yaml.dump(options, output)

        # Create the sockets
        context = zmq.Context()
        self.log_socket = context.socket(zmq.PULL)
        self.controler = context.socket(zmq.ROUTER)
        self.controler.setsockopt(zmq.IDENTITY, b"lava-logs")
        # Limit the number of messages in the queue
        self.controler.setsockopt(zmq.SNDHWM, 2)
        # From http://api.zeromq.org/4-2:zmq-setsockopt#toc5
        # "Immediately readies that connection for data transfer with the master"
        self.controler.setsockopt(zmq.CONNECT_RID, b"master")

        if options["ipv6"]:
            self.logger.info("[INIT] Enabling IPv6")
            self.log_socket.setsockopt(zmq.IPV6, 1)
            self.controler.setsockopt(zmq.IPV6, 1)

        if options["encrypt"]:
            self.logger.info("[INIT] Starting encryption")
            try:
                self.auth = ThreadAuthenticator(context)
                self.auth.start()
                self.logger.debug(
                    "[INIT] Opening master certificate: %s", options["master_cert"]
                )
                master_public, master_secret = zmq.auth.load_certificate(
                    options["master_cert"]
                )
                self.logger.debug(
                    "[INIT] Using slaves certificates from: %s", options["slaves_certs"]
                )
                self.auth.configure_curve(domain="*", location=options["slaves_certs"])
            except OSError as err:
                self.logger.error("[INIT] %s", err)
                self.auth.stop()
                return
            self.log_socket.curve_publickey = master_public
            self.log_socket.curve_secretkey = master_secret
            self.log_socket.curve_server = True
            self.controler.curve_publickey = master_public
            self.controler.curve_secretkey = master_secret
            self.controler.curve_serverkey = master_public

        self.logger.debug("[INIT] Watching %s", options["slaves_certs"])
        self.cert_dir_path = options["slaves_certs"]
        self.inotify_fd = watch_directory(options["slaves_certs"])
        if self.inotify_fd is None:
            self.logger.error("[INIT] Unable to start inotify")

        self.log_socket.bind(options["socket"])
        self.controler.connect(options["master_socket"])

        # Poll on the sockets. This allow to have a
        # nice timeout along with polling.
        self.poller = zmq.Poller()
        self.poller.register(self.log_socket, zmq.POLLIN)
        self.poller.register(self.controler, zmq.POLLIN)
        if self.inotify_fd is not None:
            self.poller.register(os.fdopen(self.inotify_fd), zmq.POLLIN)

        # Translate signals into zmq messages
        (self.pipe_r, _) = self.setup_zmq_signal_handler()
        self.poller.register(self.pipe_r, zmq.POLLIN)

        self.logger.info("[INIT] listening for logs")
        # PING right now: the master is waiting for this message to start
        # scheduling.
        self.controler.send_multipart([b"master", b"PING"])

        try:
            self.main_loop()
        except BaseException as exc:
            self.logger.error("[EXIT] Unknown exception raised, leaving!")
            self.logger.exception(exc)

        # Close the controler socket
        self.controler.close(linger=0)
        self.poller.unregister(self.controler)

        # Carefully close the logging socket as we don't want to lose messages
        self.logger.info("[EXIT] Disconnect logging socket and process messages")
        endpoint = u(self.log_socket.getsockopt(zmq.LAST_ENDPOINT))
        self.logger.debug("[EXIT] unbinding from '%s'", endpoint)
        self.log_socket.unbind(endpoint)

        # Empty the queue
        try:
            while self.wait_for_messages(True):
                # Flush test cases cache for every iteration because we might
                # get killed soon.
                self.flush_test_cases()
        except BaseException as exc:
            self.logger.error("[EXIT] Unknown exception raised, leaving!")
            self.logger.exception(exc)
        finally:
            # Last flush
            self.flush_test_cases()
            self.logger.info("[EXIT] Closing the logging socket: the queue is empty")
            self.log_socket.close()
            if options["encrypt"]:
                self.auth.stop()
            context.term()

    def flush_test_cases(self):
        if not self.test_cases:
            return

        # Try to save into the database
        try:
            TestCase.objects.bulk_create(self.test_cases)
            self.logger.info("Saving %d test cases", len(self.test_cases))
            self.test_cases = []
        except DatabaseError as exc:
            self.logger.error("Unable to flush the test cases")
            self.logger.exception(exc)
            self.logger.warning(
                "Saving test cases one by one and dropping the faulty ones"
            )
            saved = 0
            for tc in self.test_cases:
                with contextlib.suppress(DatabaseError):
                    tc.save()
                    saved += 1
            self.logger.info(
                "%d test cases saved, %d dropped", saved, len(self.test_cases) - saved
            )
            self.test_cases = []

    def main_loop(self):
        last_gc = time.time()
        last_bulk_create = time.time()

        # Wait for messages
        # TODO: fix timeout computation
        while self.wait_for_messages(False):
            now = time.time()

            # Dump TestCase into the database
            if now - last_bulk_create > BULK_CREATE_TIMEOUT:
                last_bulk_create = now
                self.flush_test_cases()

            # Close old file handlers
            if now - last_gc > FD_TIMEOUT:
                last_gc = now
                # Iterate while removing keys is not compatible with iterator
                for job_id in list(self.jobs.keys()):
                    if now - self.jobs[job_id].last_usage > FD_TIMEOUT:
                        self.logger.info("[%s] closing log file", job_id)
                        self.jobs[job_id].close()
                        del self.jobs[job_id]

            # Ping the master
            if now - self.last_ping > self.ping_interval:
                self.logger.debug("PING => master")
                self.last_ping = now
                self.controler.send_multipart([b"master", b"PING"])

    def wait_for_messages(self, leaving):
        try:
            try:
                sockets = dict(self.poller.poll(TIMEOUT * 1000))
            except zmq.error.ZMQError as exc:
                self.logger.error("[POLL] zmq error: %s", str(exc))
                return True

            # Messages
            if sockets.get(self.log_socket) == zmq.POLLIN:
                self.logging_socket()
                return True

            # Signals
            elif sockets.get(self.pipe_r) == zmq.POLLIN:
                # remove the message from the queue
                os.read(self.pipe_r, 1)

                if not leaving:
                    self.logger.info("[POLL] received a signal, leaving")
                    return False
                else:
                    self.logger.warning(
                        "[POLL] signal already handled, please wait for the process to exit"
                    )
                    return True

            # Pong received
            elif sockets.get(self.controler) == zmq.POLLIN:
                self.controler_socket()
                return True

            # Inotify socket
            if sockets.get(self.inotify_fd) == zmq.POLLIN:
                os.read(self.inotify_fd, 4096)
                self.logger.debug(
                    "[AUTH] Reloading certificates from %s", self.cert_dir_path
                )
                self.auth.configure_curve(domain="*", location=self.cert_dir_path)

            # Nothing received
            else:
                return not leaving

        except (OperationalError, InterfaceError):
            self.logger.info("[RESET] database connection reset")
            connection.close()
        return True

    def logging_socket(self):
        msg = self.log_socket.recv_multipart()
        try:
            (job_id, message) = (
                u(m) for m in msg
            )  # pylint: disable=unbalanced-tuple-unpacking
        except ValueError:
            # do not let a bad message stop the master.
            self.logger.error("[POLL] failed to parse log message, skipping: %s", msg)
            return

        try:
            scanned = yaml.load(message, Loader=yaml.CLoader)
        except yaml.YAMLError:
            self.logger.error("[%s] data are not valid YAML, dropping", job_id)
            return

        # Look for "results" level
        try:
            message_lvl = scanned["lvl"]
            message_msg = scanned["msg"]
        except TypeError:
            self.logger.error("[%s] not a dictionary, dropping", job_id)
            return
        except KeyError:
            self.logger.error(
                '[%s] invalid log line, missing "lvl" or "msg" keys: %s',
                job_id,
                message,
            )
            return

        # Find the handler (if available)
        if job_id not in self.jobs:
            # Query the database for the job
            try:
                job = TestJob.objects.get(id=job_id)
            except TestJob.DoesNotExist:
                self.logger.error("[%s] unknown job id", job_id)
                return

            self.logger.info("[%s] receiving logs from a new job", job_id)
            # Create the sub directories (if needed)
            mkdir(job.output_dir)
            self.jobs[job_id] = JobHandler(job)

        # For 'event', send an event and log as 'debug'
        if message_lvl == "event":
            self.logger.debug("[%s] event: %s", job_id, message_msg)
            send_event(".event", "lavaserver", {"message": message_msg, "job": job_id})
            message_lvl = "debug"
        # For 'marker', save in the database and log as 'debug'
        elif message_lvl == "marker":
            # TODO: save on the file system in case of lava-logs restart
            m_type = message_msg.get("type")
            case = message_msg.get("case")
            if m_type is None or case is None:
                self.logger.error("[%s] invalid marker: %s", job_id, message_msg)
                return
            self.jobs[job_id].markers.setdefault(case, {})[m_type] = self.jobs[
                job_id
            ].line_count()
            # This is in fact the previous line
            self.jobs[job_id].markers[case][m_type] -= 1
            self.logger.debug(
                "[%s] marker: %s line: %s",
                job_id,
                message_msg,
                self.jobs[job_id].markers[case][m_type],
            )
            return

        # Mark the file handler as used
        self.jobs[job_id].last_usage = time.time()
        # The format is a list of dictionaries
        self.jobs[job_id].write("- %s" % message)

        if message_lvl == "results":
            try:
                job = TestJob.objects.get(pk=job_id)
            except TestJob.DoesNotExist:
                self.logger.error("[%s] unknown job id", job_id)
                return
            meta_filename = create_metadata_store(message_msg, job)
            new_test_case = map_scanned_results(
                results=message_msg,
                job=job,
                markers=self.jobs[job_id].markers,
                meta_filename=meta_filename,
            )

            if new_test_case is None:
                self.logger.warning(
                    "[%s] unable to map scanned results: %s", job_id, message
                )
            else:
                self.test_cases.append(new_test_case)

            # Look for lava.job result
            if (
                message_msg.get("definition") == "lava"
                and message_msg.get("case") == "job"
            ):
                # Flush cached test cases
                self.flush_test_cases()

                if message_msg.get("result") == "pass":
                    health = TestJob.HEALTH_COMPLETE
                    health_msg = "Complete"
                else:
                    health = TestJob.HEALTH_INCOMPLETE
                    health_msg = "Incomplete"
                self.logger.info("[%s] job status: %s", job_id, health_msg)

                infrastructure_error = message_msg.get("error_type") in [
                    "Bug",
                    "Configuration",
                    "Infrastructure",
                ]
                if infrastructure_error:
                    self.logger.info("[%s] Infrastructure error", job_id)

                # Update status.
                with transaction.atomic():
                    # TODO: find a way to lock actual_device
                    job = TestJob.objects.select_for_update().get(id=job_id)
                    job.go_state_finished(health, infrastructure_error)
                    job.save()

        # n.b. logging here would produce a log entry for every message in every job.

    def controler_socket(self):
        msg = self.controler.recv_multipart()
        try:
            master_id = u(msg[0])
            action = u(msg[1])
            ping_interval = int(msg[2])

            if master_id != "master":
                self.logger.error(
                    "Invalid master id '%s'. Should be 'master'", master_id
                )
                return
            if action != "PONG":
                self.logger.error("Invalid answer '%s'. Should be 'PONG'", action)
                return
        except (IndexError, ValueError):
            self.logger.error("Invalid message '%s'", msg)
            return

        if ping_interval < TIMEOUT:
            self.logger.error("invalid ping interval (%d) too small", ping_interval)
            return

        self.logger.debug("master => PONG(%d)", ping_interval)
        self.ping_interval = ping_interval
