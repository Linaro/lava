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

# pylint: disable=wrong-import-order

import contextlib
import jinja2
import simplejson
import lzma
import os
import time
import yaml
import zmq
import zmq.auth
from zmq.utils.strtypes import b, u
from zmq.auth.thread import ThreadAuthenticator

from django.conf import settings
from django.db import connection, transaction
from django.db.utils import OperationalError, InterfaceError
from django.utils import timezone

from lava_results_app.models import TestCase, TestSuite
from lava_scheduler_app.dbutils import parse_job_description
from lava_scheduler_app.models import TestJob, Worker
from lava_scheduler_app.scheduler import schedule
from lava_scheduler_app.utils import mkdir
from lava_server.cmdutils import LAVADaemonCommand, watch_directory


# pylint: disable=no-member,bad-continuation

# Current version of the protocol
# The slave does send the protocol version along with the HELLO and HELLO_RETRY
# messages. If both version are not identical, the connection is refused by the
# master.
PROTOCOL_VERSION = 3

# Slave ping interval and timeout
PING_INTERVAL = 20
DISPATCHER_TIMEOUT = 3 * PING_INTERVAL
SCHEDULE_INTERVAL = 20

# Log format
FORMAT = "%(asctime)-15s %(levelname)7s %(message)s"

# Configuration files
ENV_PATH = "/etc/lava-server/env.yaml"
ENV_DUT_PATH = "/etc/lava-server/env.dut.yaml"
DISPATCHERS_PATH = "/etc/lava-server/dispatcher.d"


def send_multipart_u(sock, data):
    """ Wrapper around send_multipart that encode data as bytes.

    :param sock: The socket to use
    :param data: Data to convert to byte strings
    """
    return sock.send_multipart([b(d) for d in data])


class SlaveDispatcher:  # pylint: disable=too-few-public-methods
    def __init__(self, hostname, online=True):
        self.hostname = hostname
        self.last_msg = time.time() if online else 0
        # Set the opposite for alive and go_offline to work
        self.online = not online
        # lookup the worker and set the state
        if online:
            self.alive()
        else:
            self.go_offline()

    def alive(self):
        self.last_msg = time.time()
        self.online = True
        with transaction.atomic():
            try:
                worker = Worker.objects.select_for_update().get(hostname=self.hostname)
            except Worker.DoesNotExist:
                Worker.objects.create(
                    hostname=self.hostname,
                    description="Created by lava-master (%s)" % timezone.now(),
                )
                worker = Worker.objects.select_for_update().get(hostname=self.hostname)
                worker.log_admin_entry(None, "Created by lava-master", addition=True)

            if worker.state == Worker.STATE_OFFLINE:
                worker.go_state_online()
            worker.last_ping = timezone.now()
            worker.save()

    def go_offline(self):
        if self.online:
            self.online = False
            # If the worker does not exist, just skip the update
            with contextlib.suppress(Worker.DoesNotExist), transaction.atomic():
                worker = Worker.objects.select_for_update().get(hostname=self.hostname)
                worker.go_state_offline()
                worker.save()


def load_optional_yaml_file(filename, fallback=None):
    """
    Returns the string after checking for YAML errors which would cause issues later.
    Only raise an error if the file exists but is not readable or parsable
    """
    try:
        with open(filename, "r") as f_in:
            data_str = f_in.read()
        yaml.safe_load(data_str)
        return data_str
    except FileNotFoundError:
        # This is ok if the file does not exist
        if fallback is None:
            return ""
        # Use the fallback filename
        return load_optional_yaml_file(fallback)
    except yaml.YAMLError:
        # Raise an OSError because the caller uses yaml.YAMLError for a
        # specific usage. Allows here to specify the faulty filename.
        raise OSError("", "Not a valid YAML file", filename)


class Command(LAVADaemonCommand):
    """
    worker_host is the hostname of the worker this field is set by the admin
    and could therefore be empty in a misconfigured instance.
    """

    logger = None
    help = "LAVA dispatcher master"
    default_logfile = "/var/log/lava-server/lava-master.log"

    def __init__(self, *args, **options):
        super().__init__(*args, **options)
        self.auth = None
        self.controler = None
        self.event_socket = None
        self.poller = None
        self.pipe_r = None
        self.inotify_fd = None
        # List of logs
        # List of known dispatchers. At startup do not load this from the
        # database. This will help to know if the slave as restarted or not.
        self.dispatchers = {"lava-logs": SlaveDispatcher("lava-logs", online=False)}
        self.events = {"canceling": set(), "available_dt": set()}

    def add_arguments(self, parser):
        super().add_arguments(parser)
        net = parser.add_argument_group("network")
        net.add_argument(
            "--master-socket",
            default="tcp://*:5556",
            help="Socket for master-slave communication. Default: tcp://*:5556",
        )
        net.add_argument(
            "--event-url", default="tcp://localhost:5500", help="URL of the publisher"
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

    def send_status(self, hostname):
        """
        The master crashed, send a STATUS message to get the current state of jobs
        """
        jobs = TestJob.objects.filter(
            actual_device__worker_host__hostname=hostname, state=TestJob.STATE_RUNNING
        )
        for job in jobs:
            self.logger.info(
                "[%d] STATUS => %s (%s)", job.id, hostname, job.actual_device.hostname
            )
            send_multipart_u(self.controler, [hostname, "STATUS", str(job.id)])

    def dispatcher_alive(self, hostname):
        if hostname not in self.dispatchers:
            # The server crashed: send a STATUS message
            self.logger.warning("Unknown dispatcher <%s> (server crashed)", hostname)
            self.dispatchers[hostname] = SlaveDispatcher(hostname)
            self.send_status(hostname)

        # Mark the dispatcher as alive
        self.dispatchers[hostname].alive()

    def controler_socket(self):
        try:
            # We need here to use the zmq.NOBLOCK flag, otherwise we could block
            # the whole main loop where this function is called.
            msg = self.controler.recv_multipart(zmq.NOBLOCK)
        except zmq.error.Again:
            return False
        # This is way to verbose for production and should only be activated
        # by (and for) developers
        # self.logger.debug("[CC] Receiving: %s", msg)

        try:
            # 1: the hostname (see ZMQ documentation)
            hostname = u(msg[0])
            # 2: the action
            action = u(msg[1])
        except (IndexError, ValueError):
            self.logger.error("Invalid message from <%s> '%s'", hostname, msg)
            return True

        # Check that lava-logs only send PINGs
        if hostname == "lava-logs" and action != "PING":
            self.logger.error(
                "%s => %s Invalid action from log daemon", hostname, action
            )
            return True

        # Handle the actions
        if action == "HELLO" or action == "HELLO_RETRY":
            self._handle_hello(hostname, action, msg)
        elif action == "PING":
            self._handle_ping(hostname, msg)
        elif action == "END":
            self._handle_end(hostname, msg)
        elif action == "START_OK":
            self._handle_start_ok(hostname, msg)
        else:
            self.logger.error(
                "<%s> sent unknown action=%s, args=(%s)", hostname, action, msg[1:]
            )
        return True

    def read_event_socket(self):
        try:
            msg = self.event_socket.recv_multipart(zmq.NOBLOCK)
        except zmq.error.Again:
            return False

        try:
            (topic, _, dt, username, data) = (u(m) for m in msg)
            data = simplejson.loads(data)
        except ValueError:
            self.logger.error("Invalid event: %s", msg)
            return True

        if topic.endswith(".testjob"):
            if data["state"] == "Canceling":
                self.events["canceling"].add(int(data["job"]))
            elif data["state"] == "Submitted":
                if "device_type" in data:
                    self.events["available_dt"].add(data["device_type"])
        elif topic.endswith(".device"):
            if data["state"] == "Idle" and data["health"] in [
                "Good",
                "Unknown",
                "Looping",
            ]:
                self.events["available_dt"].add(data["device_type"])

        return True

    def _handle_end(self, hostname, msg):
        try:
            job_id = int(msg[2])
            error_msg = u(msg[3])
            compressed_description = msg[4]
        except (IndexError, ValueError):
            self.logger.error("Invalid message from <%s> '%s'", hostname, msg)
            return

        try:
            job = TestJob.objects.get(id=job_id)
        except TestJob.DoesNotExist:
            self.logger.error("[%d] Unknown job", job_id)
            # ACK even if the job is unknown to let the dispatcher
            # forget about it
            send_multipart_u(self.controler, [hostname, "END_OK", str(job_id)])
            return

        filename = os.path.join(job.output_dir, "description.yaml")
        # If description.yaml already exists: a END was already received
        if os.path.exists(filename):
            self.logger.info("[%d] %s => END (duplicated), skipping", job_id, hostname)
        else:
            if compressed_description:
                self.logger.info("[%d] %s => END", job_id, hostname)
            else:
                self.logger.info(
                    "[%d] %s => END (lava-run crashed, mark job as INCOMPLETE)",
                    job_id,
                    hostname,
                )
                with transaction.atomic():
                    # TODO: find a way to lock actual_device
                    job = TestJob.objects.select_for_update().get(id=job_id)

                    job.go_state_finished(TestJob.HEALTH_INCOMPLETE)
                    if error_msg:
                        self.logger.error("[%d] Error: %s", job_id, error_msg)
                        job.failure_comment = error_msg
                    job.save()

            # Create description.yaml even if it's empty
            # Allows to know when END messages are duplicated
            try:
                # Create the directory if it was not already created
                mkdir(os.path.dirname(filename))
                # TODO: check that compressed_description is not ""
                description = lzma.decompress(compressed_description)
                with open(filename, "w") as f_description:
                    f_description.write(description.decode("utf-8"))
                if description:
                    parse_job_description(job)
            except (OSError, lzma.LZMAError) as exc:
                self.logger.error("[%d] Unable to dump 'description.yaml'", job_id)
                self.logger.exception("[%d] %s", job_id, exc)

        # ACK the job and mark the dispatcher as alive
        send_multipart_u(self.controler, [hostname, "END_OK", str(job_id)])
        self.dispatcher_alive(hostname)

    def _handle_hello(self, hostname, action, msg):
        # Check the protocol version
        try:
            slave_version = int(msg[2])
        except (IndexError, ValueError):
            self.logger.error("Invalid message from <%s> '%s'", hostname, msg)
            return

        self.logger.info("%s => %s", hostname, action)
        if slave_version != PROTOCOL_VERSION:
            self.logger.error(
                "<%s> using protocol v%d while master is using v%d",
                hostname,
                slave_version,
                PROTOCOL_VERSION,
            )
            return

        send_multipart_u(self.controler, [hostname, "HELLO_OK"])
        # If the dispatcher is known and sent an HELLO, means that
        # the slave has restarted
        if hostname in self.dispatchers:
            if action == "HELLO":
                self.logger.warning("Dispatcher <%s> has RESTARTED", hostname)
            else:
                # Assume the HELLO command was received, and the
                # action succeeded.
                self.logger.warning("Dispatcher <%s> was not confirmed", hostname)
        else:
            # No dispatcher, treat HELLO and HELLO_RETRY as a normal HELLO
            # message.
            self.logger.warning("New dispatcher <%s>", hostname)
            self.dispatchers[hostname] = SlaveDispatcher(hostname)

        # Mark the dispatcher as alive
        self.dispatcher_alive(hostname)

    def _handle_ping(self, hostname, msg):
        self.logger.debug("%s => PING(%d)", hostname, PING_INTERVAL)
        # Send back a signal
        send_multipart_u(self.controler, [hostname, "PONG", str(PING_INTERVAL)])
        self.dispatcher_alive(hostname)

    def _handle_start_ok(self, hostname, msg):
        try:
            job_id = int(msg[2])
        except (IndexError, ValueError):
            self.logger.error("Invalid message from <%s> '%s'", hostname, msg)
            return
        self.logger.info("[%d] %s => START_OK", job_id, hostname)
        try:
            with transaction.atomic():
                # TODO: find a way to lock actual_device
                job = TestJob.objects.select_for_update().get(id=job_id)
                job.go_state_running()
                job.save()
        except TestJob.DoesNotExist:
            self.logger.error("[%d] Unknown job", job_id)
        else:
            self.dispatcher_alive(hostname)

    def export_definition(self, job):  # pylint: disable=no-self-use
        job_def = yaml.safe_load(job.definition)
        job_def["compatibility"] = job.pipeline_compatibility

        # no need for the dispatcher to retain comments
        return yaml.dump(job_def)

    def save_job_config(self, job, device_cfg, env_str, env_dut_str, dispatcher_cfg):
        output_dir = job.output_dir
        mkdir(output_dir)
        with open(os.path.join(output_dir, "job.yaml"), "w") as f_out:
            f_out.write(self.export_definition(job))
        with open(os.path.join(output_dir, "device.yaml"), "w") as f_out:
            yaml.dump(device_cfg, f_out)
        if env_str:
            with open(os.path.join(output_dir, "env.yaml"), "w") as f_out:
                f_out.write(env_str)
        if env_dut_str:
            with open(os.path.join(output_dir, "env.dut.yaml"), "w") as f_out:
                f_out.write(env_dut_str)
        if dispatcher_cfg:
            with open(os.path.join(output_dir, "dispatcher.yaml"), "w") as f_out:
                f_out.write(dispatcher_cfg)

    def start_job(self, job):
        # Load job definition to get the variables for template
        # rendering
        job_def = yaml.safe_load(job.definition)
        job_ctx = job_def.get("context", {})

        device = job.actual_device
        worker = device.worker_host

        # TODO: check that device_cfg is not None!
        device_cfg = device.load_configuration(job_ctx)

        # Try to load the dispatcher specific files and then fallback to the
        # default configuration files.
        env_str = load_optional_yaml_file(
            os.path.join(DISPATCHERS_PATH, worker.hostname, "env.yaml"), ENV_PATH
        )
        env_dut_str = load_optional_yaml_file(
            os.path.join(DISPATCHERS_PATH, worker.hostname, "env.dut.yaml"),
            ENV_DUT_PATH,
        )
        dispatcher_cfg = load_optional_yaml_file(
            os.path.join(DISPATCHERS_PATH, worker.hostname, "dispatcher.yaml"),
            os.path.join(DISPATCHERS_PATH, "%s.yaml" % worker.hostname),
        )

        self.save_job_config(job, device_cfg, env_str, env_dut_str, dispatcher_cfg)
        self.logger.info(
            "[%d] START => %s (%s)", job.id, worker.hostname, device.hostname
        )
        send_multipart_u(
            self.controler,
            [
                worker.hostname,
                "START",
                str(job.id),
                self.export_definition(job),
                yaml.dump(device_cfg),
                dispatcher_cfg,
                env_str,
                env_dut_str,
            ],
        )

        # For multinode jobs, start the dynamic connections
        parent = job
        for sub_job in job.sub_jobs_list:
            if sub_job == parent or not sub_job.dynamic_connection:
                continue

            # inherit only enough configuration for dynamic_connection operation
            self.logger.info(
                "[%d] Trimming dynamic connection device configuration.", sub_job.id
            )
            min_device_cfg = parent.actual_device.minimise_configuration(device_cfg)

            self.save_job_config(
                sub_job, min_device_cfg, env_str, env_dut_str, dispatcher_cfg
            )
            self.logger.info(
                "[%d] START => %s (connection)", sub_job.id, worker.hostname
            )
            send_multipart_u(
                self.controler,
                [
                    worker.hostname,
                    "START",
                    str(sub_job.id),
                    self.export_definition(sub_job),
                    yaml.dump(min_device_cfg),
                    dispatcher_cfg,
                    env_str,
                    env_dut_str,
                ],
            )

    def start_jobs(self, jobs=None):
        """
        Loop on all scheduled jobs and send the START message to the slave.
        """
        # make the request atomic
        query = TestJob.objects.select_for_update()
        # Only select test job that are ready
        query = query.filter(state=TestJob.STATE_SCHEDULED)
        # Only start jobs on online workers
        query = query.filter(actual_device__worker_host__state=Worker.STATE_ONLINE)
        # exclude test job without a device: they are special test jobs like
        # dynamic connection.
        query = query.exclude(actual_device=None)
        # Allow for partial scheduling
        if jobs is not None:
            query = query.filter(id__in=jobs)

        # Loop on all jobs
        for job in query:
            msg = None
            try:
                self.start_job(job)
            except jinja2.TemplateNotFound as exc:
                self.logger.error("[%d] Template not found: '%s'", job.id, exc.message)
                msg = "Template not found: '%s'" % exc.message
            except jinja2.TemplateSyntaxError as exc:
                self.logger.error(
                    "[%d] Template syntax error in '%s', line %d: %s",
                    job.id,
                    exc.name,
                    exc.lineno,
                    exc.message,
                )
                msg = "Template syntax error in '%s', line %d: %s" % (
                    exc.name,
                    exc.lineno,
                    exc.message,
                )
            except OSError as exc:
                self.logger.error(
                    "[%d] Unable to read '%s': %s", job.id, exc.filename, exc.strerror
                )
                msg = "Cannot open '%s': %s" % (exc.filename, exc.strerror)
            except yaml.YAMLError as exc:
                self.logger.error(
                    "[%d] Unable to parse job definition: %s", job.id, exc
                )
                msg = "Cannot parse job definition: %s" % exc

            if msg:
                # Add the error as lava.job result
                metadata = {
                    "case": "job",
                    "definition": "lava",
                    "error_type": "Infrastructure",
                    "error_msg": msg,
                    "result": "fail",
                }
                suite, _ = TestSuite.objects.get_or_create(name="lava", job=job)
                TestCase.objects.create(
                    name="job",
                    suite=suite,
                    result=TestCase.RESULT_FAIL,
                    metadata=yaml.dump(metadata),
                )
                job.go_state_finished(TestJob.HEALTH_INCOMPLETE, True)
                job.save()

    def cancel_jobs(self, partial=False):
        # make the request atomic
        query = TestJob.objects.select_for_update()
        # Only select the test job that are canceling
        query = query.filter(state=TestJob.STATE_CANCELING)
        # Only cancel jobs on online workers
        query = query.filter(actual_device__worker_host__state=Worker.STATE_ONLINE)

        # Allow for partial canceling
        if partial:
            query = query.filter(id__in=list(self.events["canceling"]))

        # Loop on all jobs
        for job in query:
            worker = (
                job.lookup_worker
                if job.dynamic_connection
                else job.actual_device.worker_host
            )
            self.logger.info("[%d] CANCEL => %s", job.id, worker.hostname)
            send_multipart_u(self.controler, [worker.hostname, "CANCEL", str(job.id)])

    def handle(self, *args, **options):
        # Initialize logging.
        self.setup_logging("lava-master", options["level"], options["log_file"], FORMAT)

        self.logger.info("[INIT] Dropping privileges")
        if not self.drop_privileges(options["user"], options["group"]):
            self.logger.error("[INIT] Unable to drop privileges")
            return

        filename = os.path.join(settings.MEDIA_ROOT, "lava-master-config.yaml")
        self.logger.debug("[INIT] Dumping config to %s", filename)
        with open(filename, "w") as output:
            yaml.dump(options, output)

        self.logger.info("[INIT] Marking all workers as offline")
        with transaction.atomic():
            for worker in Worker.objects.select_for_update().all():
                worker.go_state_offline()
                worker.save()

        # Create the sockets
        context = zmq.Context()
        self.controler = context.socket(zmq.ROUTER)
        self.event_socket = context.socket(zmq.SUB)

        if options["ipv6"]:
            self.logger.info("[INIT] Enabling IPv6")
            self.controler.setsockopt(zmq.IPV6, 1)
            self.event_socket.setsockopt(zmq.IPV6, 1)

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
                self.logger.error(err)
                self.auth.stop()
                return
            self.controler.curve_publickey = master_public
            self.controler.curve_secretkey = master_secret
            self.controler.curve_server = True

            self.logger.debug("[INIT] Watching %s", options["slaves_certs"])
            self.inotify_fd = watch_directory(options["slaves_certs"])
            if self.inotify_fd is None:
                self.logger.error("[INIT] Unable to start inotify")

        self.controler.setsockopt(zmq.IDENTITY, b"master")
        # From http://api.zeromq.org/4-2:zmq-setsockopt#toc42
        # "If two clients use the same identity when connecting to a ROUTER
        # [...] the ROUTER socket shall hand-over the connection to the new
        # client and disconnect the existing one."
        self.controler.setsockopt(zmq.ROUTER_HANDOVER, 1)
        self.controler.bind(options["master_socket"])

        # Set the topic and connect
        self.event_socket.setsockopt(zmq.SUBSCRIBE, b(settings.EVENT_TOPIC))
        self.event_socket.connect(options["event_url"])

        # Poll on the sockets. This allow to have a
        # nice timeout along with polling.
        self.poller = zmq.Poller()
        self.poller.register(self.controler, zmq.POLLIN)
        self.poller.register(self.event_socket, zmq.POLLIN)
        if self.inotify_fd is not None:
            self.poller.register(os.fdopen(self.inotify_fd), zmq.POLLIN)

        # Translate signals into zmq messages
        (self.pipe_r, _) = self.setup_zmq_signal_handler()
        self.poller.register(self.pipe_r, zmq.POLLIN)

        self.logger.info("[INIT] LAVA master has started.")
        self.logger.info("[INIT] Using protocol version %d", PROTOCOL_VERSION)

        try:
            self.main_loop(options)
        except BaseException as exc:
            self.logger.error("[CLOSE] Unknown exception raised, leaving!")
            self.logger.exception(exc)
        finally:
            # Drop controler socket: the protocol does handle lost messages
            self.logger.info(
                "[CLOSE] Closing the controler socket and dropping messages"
            )
            self.controler.close(linger=0)
            self.event_socket.close(linger=0)
            if options["encrypt"]:
                self.auth.stop()
            context.term()

    def main_loop(self, options):
        last_schedule = last_dispatcher_check = time.time()

        while True:
            try:
                try:
                    # Compute the timeout
                    now = time.time()
                    timeout = min(
                        SCHEDULE_INTERVAL - (now - last_schedule),
                        PING_INTERVAL - (now - last_dispatcher_check),
                    )
                    # If some actions are remaining, decrease the timeout
                    if any([self.events[k] for k in self.events.keys()]):
                        timeout = min(timeout, 2)
                    # Wait at least for 1ms
                    timeout = max(timeout * 1000, 1)

                    # Wait for data or a timeout
                    sockets = dict(self.poller.poll(timeout))
                except zmq.error.ZMQError:
                    continue

                if sockets.get(self.pipe_r) == zmq.POLLIN:
                    self.logger.info("[POLL] Received a signal, leaving")
                    break

                # Command socket
                if sockets.get(self.controler) == zmq.POLLIN:
                    while self.controler_socket():  # Unqueue all pending messages
                        pass

                # Events socket
                if sockets.get(self.event_socket) == zmq.POLLIN:
                    self.logger.info("[EVENT] handling events")
                    while self.read_event_socket():  # Unqueue all pending messages
                        pass
                    # Wait for the next iteration to handle the event.
                    # In fact, the code that generated the event (lava-logs or
                    # lava-server-gunicorn) needs some time to commit the
                    # database transaction.
                    # If we are too fast, the database object won't be
                    # available (or in the right state) yet.
                    continue

                # Inotify socket
                if sockets.get(self.inotify_fd) == zmq.POLLIN:
                    os.read(self.inotify_fd, 4096)
                    self.logger.info(
                        "[AUTH] Reloading certificates from %s", options["slaves_certs"]
                    )
                    self.auth.configure_curve(
                        domain="*", location=options["slaves_certs"]
                    )

                # Check dispatchers status
                now = time.time()
                if now - last_dispatcher_check > PING_INTERVAL:
                    for hostname, dispatcher in self.dispatchers.items():
                        if (
                            dispatcher.online
                            and now - dispatcher.last_msg > DISPATCHER_TIMEOUT
                        ):
                            if hostname == "lava-logs":
                                self.logger.error("[STATE] lava-logs goes OFFLINE")
                            else:
                                self.logger.error(
                                    "[STATE] Dispatcher <%s> goes OFFLINE", hostname
                                )
                            self.dispatchers[hostname].go_offline()
                    last_dispatcher_check = now

                # Limit accesses to the database. This will also limit the rate of
                # CANCEL and START messages
                if time.time() - last_schedule > SCHEDULE_INTERVAL:
                    if self.dispatchers["lava-logs"].online:
                        schedule(self.logger)

                        # Dispatch scheduled jobs
                        with transaction.atomic():
                            self.start_jobs()
                    else:
                        self.logger.warning("lava-logs is offline: can't schedule jobs")

                    # Handle canceling jobs
                    with transaction.atomic():
                        self.cancel_jobs()

                    # Do not count the time taken to schedule jobs
                    last_schedule = time.time()
                else:
                    # Cancel the jobs and remove the jobs from the set
                    if self.events["canceling"]:
                        with transaction.atomic():
                            self.cancel_jobs(partial=True)
                        self.events["canceling"] = set()
                    # Schedule for available device-types
                    if self.events["available_dt"]:
                        jobs = schedule(self.logger, self.events["available_dt"])
                        self.events["available_dt"] = set()
                        # Dispatch scheduled jobs
                        with transaction.atomic():
                            self.start_jobs(jobs)

            except (OperationalError, InterfaceError):
                self.logger.info("[RESET] database connection reset.")
                # Closing the database connection will force Django to reopen
                # the connection
                connection.close()
                time.sleep(2)
