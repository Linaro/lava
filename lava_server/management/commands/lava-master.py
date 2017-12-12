# Copyright (C) 2015 Linaro Limited
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

# pylint: disable=wrong-import-order

from contextlib import contextmanager
import errno
import jinja2
import lzma
import os
import time
import yaml
import zmq
import zmq.auth
from zmq.auth.thread import ThreadAuthenticator

from django.db import connection, transaction
from django.db.utils import OperationalError, InterfaceError
from django.utils import timezone

from lava_scheduler_app.dbutils import (
    parse_job_description,
)
from lava_scheduler_app.models import TestJob, Worker
from lava_scheduler_app.utils import mkdir
from lava_scheduler_app.scheduler import schedule
from lava_server.cmdutils import LAVADaemonCommand


# pylint: disable=no-member,too-many-branches,too-many-statements,too-many-locals

# Current version of the protocol
# The slave does send the protocol version along with the HELLO and HELLO_RETRY
# messages. If both version are not identical, the connection is refused by the
# master.
PROTOCOL_VERSION = 2

# Slave ping interval and timeout
PING_INTERVAL = 20
DISPATCHER_TIMEOUT = 3 * PING_INTERVAL
SCHEDULE_INTERVAL = 20

# Log format
FORMAT = '%(asctime)-15s %(levelname)7s %(message)s'


@contextmanager
def suppress(kls):
    """ Suppress the given exception """
    try:
        yield
    except kls:
        pass


class SlaveDispatcher(object):  # pylint: disable=too-few-public-methods

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
                Worker.objects.create(hostname=self.hostname, description="Created by lava-master (%s)" % timezone.now())
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
            with suppress(Worker.DoesNotExist), transaction.atomic():
                worker = Worker.objects.select_for_update().get(hostname=self.hostname)
                worker.go_state_offline()
                worker.save()


def load_optional_yaml_file(filename):
    """
    Returns the string after checking for YAML errors which would cause issues later.
    Only raise an error if the file exists but is not readable or parsable
    """
    try:
        with open(filename, "r") as f_in:
            data_str = f_in.read()
        yaml.safe_load(data_str)
        return data_str
    except IOError as exc:
        # This is ok if the file does not exist
        if exc.errno == errno.ENOENT:
            return ''
        raise
    except yaml.YAMLError:
        # Raise an IOError because the caller uses yaml.YAMLError for a
        # specific usage. Allows here to specify the faulty filename.
        raise IOError("", "Not a valid YAML file", filename)


class Command(LAVADaemonCommand):
    """
    worker_host is the hostname of the worker this field is set by the admin
    and could therefore be empty in a misconfigured instance.
    """
    logger = None
    help = "LAVA dispatcher master"
    default_logfile = "/var/log/lava-server/lava-master.log"

    def __init__(self, *args, **options):
        super(Command, self).__init__(*args, **options)
        self.controler = None
        # List of logs
        # List of known dispatchers. At startup do not load this from the
        # database. This will help to know if the slave as restarted or not.
        self.dispatchers = {"lava-logs": SlaveDispatcher("lava-logs", online=False)}

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        # Important: ensure share/env.yaml is put into /etc/ by setup.py in packaging.
        config = parser.add_argument_group("dispatcher config")

        config.add_argument('--env',
                            default="/etc/lava-server/env.yaml",
                            help="Environment variables for the dispatcher processes. "
                                 "Default: /etc/lava-server/env.yaml")
        config.add_argument('--env-dut',
                            default="/etc/lava-server/env.dut.yaml",
                            help="Environment variables for device under test. "
                                 "Default: /etc/lava-server/env.dut.yaml")
        config.add_argument('--dispatchers-config',
                            default="/etc/lava-server/dispatcher.d",
                            help="Directory that might contain dispatcher specific configuration")

        net = parser.add_argument_group("network")
        net.add_argument('--master-socket',
                         default='tcp://*:5556',
                         help="Socket for master-slave communication. Default: tcp://*:5556")
        net.add_argument('--ipv6', default=False, action='store_true',
                         help="Enable IPv6 on the listening sockets")
        net.add_argument('--encrypt', default=False, action='store_true',
                         help="Encrypt messages")
        net.add_argument('--master-cert',
                         default='/etc/lava-dispatcher/certificates.d/master.key_secret',
                         help="Certificate for the master socket")
        net.add_argument('--slaves-certs',
                         default='/etc/lava-dispatcher/certificates.d',
                         help="Directory for slaves certificates")

    def send_status(self, hostname):
        """
        The master crashed, send a STATUS message to get the current state of jobs
        """
        jobs = TestJob.objects.filter(actual_device__worker_host__hostname=hostname,
                                      is_pipeline=True,
                                      state=TestJob.STATE_RUNNING)
        for job in jobs:
            self.logger.info("[%d] STATUS => %s (%s)", job.id, hostname,
                             job.actual_device.hostname)
            self.controler.send_multipart([hostname, 'STATUS', str(job.id)])

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

        # 1: the hostname (see ZMQ documentation)
        hostname = msg[0]
        # 2: the action
        action = msg[1]

        # Check that lava-logs only send PINGs
        if hostname == "lava-logs" and action != "PING":
            self.logger.error("%s => %s Invalid action from log daemon",
                              hostname, action)
            return True

        # Handle the actions
        if action == 'HELLO' or action == 'HELLO_RETRY':
            return self._handle_hello(hostname, action, msg)
        elif action == 'PING':
            return self._handle_ping(hostname, action, msg)
        elif action == 'END':
            return self._handle_end(hostname, action, msg)
        elif action == 'START_OK':
            return self._handle_start_ok(hostname, action, msg)
        else:
            self.logger.error("<%s> sent unknown action=%s, args=(%s)",
                              hostname, action, msg[1:])
            return True

    def _handle_end(self, hostname, action, msg):  # pylint: disable=unused-argument
        try:
            job_id = int(msg[2])
            error_msg = msg[3]
            compressed_description = msg[4]
        except (IndexError, ValueError):
            self.logger.error("Invalid message from <%s> '%s'", hostname, msg)
            return True

        try:
            job = TestJob.objects.get(id=job_id)
        except TestJob.DoesNotExist:
            self.logger.error("[%d] Unknown job", job_id)
            # ACK even if the job is unknown to let the dispatcher
            # forget about it
            self.controler.send_multipart([hostname, 'END_OK', str(job_id)])
            return True

        filename = os.path.join(job.output_dir, 'description.yaml')
        # If description.yaml already exists: a END was already received
        if os.path.exists(filename):
            self.logger.info("[%d] %s => END (duplicated), skipping", job_id, hostname)
        else:
            if compressed_description:
                self.logger.info("[%d] %s => END", job_id, hostname)
            else:
                self.logger.info("[%d] %s => END (lava-run crashed, mark job as INCOMPLETE)",
                                 job_id, hostname)
                if error_msg:
                    self.logger.error("[%d] Error: %s", job_id, error_msg)

                with transaction.atomic():
                    # TODO: find a way to lock actual_device
                    job = TestJob.objects.select_for_update() \
                                         .get(id=job_id)
                    # TODO: use the failure message
                    job.go_state_finished(TestJob.HEALTH_INCOMPLETE)
                    job.save()

            # Create description.yaml even if it's empty
            # Allows to know when END messages are duplicated
            try:
                # Create the directory if it was not already created
                mkdir(os.path.dirname(filename))
                description = lzma.decompress(compressed_description)
                with open(filename, 'w') as f_description:
                    f_description.write(description)
                if description:
                    parse_job_description(job)
            except (IOError, lzma.error) as exc:
                self.logger.error("[%d] Unable to dump 'description.yaml'",
                                  job_id)
                self.logger.exception("[%d] %s", job_id, exc)

        # ACK the job and mark the dispatcher as alive
        self.controler.send_multipart([hostname, 'END_OK', str(job_id)])
        self.dispatcher_alive(hostname)
        return True

    def _handle_hello(self, hostname, action, msg):
        # Check the protocol version
        try:
            slave_version = int(msg[2])
        except (IndexError, ValueError):
            self.logger.error("Invalid message from <%s> '%s'", hostname, msg)
            return True

        self.logger.info("%s => %s", hostname, action)
        if slave_version != PROTOCOL_VERSION:
            self.logger.error("<%s> using protocol v%d while master is using v%d",
                              hostname, slave_version, PROTOCOL_VERSION)
            return True

        self.controler.send_multipart([hostname, 'HELLO_OK'])
        # If the dispatcher is known and sent an HELLO, means that
        # the slave has restarted
        if hostname in self.dispatchers:
            if action == 'HELLO':
                self.logger.warning("Dispatcher <%s> has RESTARTED",
                                    hostname)
                # FIXME: slaves need to be allowed to restart cleanly without affecting jobs
                # as well as handling unexpected crashes.
                self._cancel_slave_dispatcher_jobs(hostname)
            else:
                # Assume the HELLO command was received, and the
                # action succeeded.
                self.logger.warning("Dispatcher <%s> was not confirmed",
                                    hostname)
        else:
            # No dispatcher, treat HELLO and HELLO_RETRY as a normal HELLO
            # message.
            self.logger.warning("New dispatcher <%s>", hostname)
            self.dispatchers[hostname] = SlaveDispatcher(hostname)
            # FIXME: slaves need to be allowed to restart cleanly without affecting jobs
            # as well as handling unexpected crashes.
            self._cancel_slave_dispatcher_jobs(hostname)

        # Mark the dispatcher as alive
        self.dispatcher_alive(hostname)

    def _handle_ping(self, hostname, action, msg):  # pylint: disable=unused-argument
        self.logger.debug("%s => PING(%d)", hostname, PING_INTERVAL)
        # Send back a signal
        self.controler.send_multipart([hostname, 'PONG', str(PING_INTERVAL)])
        self.dispatcher_alive(hostname)
        return True

    def _handle_start_ok(self, hostname, action, msg):  # pylint: disable=unused-argument
        try:
            job_id = int(msg[2])
        except (IndexError, ValueError):
            self.logger.error("Invalid message from <%s> '%s'", hostname, msg)
            return True
        self.logger.info("[%d] %s => START_OK", job_id, hostname)
        try:
            with transaction.atomic():
                # TODO: find a way to lock actual_device
                job = TestJob.objects.select_for_update() \
                                     .get(id=job_id)
                job.go_state_running()
                job.save()
        except TestJob.DoesNotExist:
            self.logger.error("[%d] Unknown job", job_id)
        else:
            self.dispatcher_alive(hostname)

    def _cancel_slave_dispatcher_jobs(self, hostname):
        """Get dispatcher jobs and cancel them.

        :param hostname: The name of the dispatcher host.
        :type hostname: string
        """
        # TODO: DB: mark the dispatcher as online in the database.
        # For the moment this should not be done by this process as
        # some dispatchers are using old and new dispatcher.

        # Mark all jobs on this dispatcher as canceled.
        # The dispatcher had (re)started, so all jobs have to be
        # finished.
        with transaction.atomic():
            # TODO: find a way to lock actual_device
            jobs = TestJob.objects.select_for_update() \
                                  .filter(actual_device__worker_host__hostname=hostname,
                                          state=TestJob.STATE_RUNNING)

            for job in jobs:
                self.logger.info("[%d] Canceling", job.id)
                job.go_state_finished(TestJob.HEALTH_CANCELED)
                job.save()

    def export_definition(self, job):  # pylint: disable=no-self-use
        job_def = yaml.load(job.definition)
        job_def['compatibility'] = job.pipeline_compatibility

        # no need for the dispatcher to retain comments
        return yaml.dump(job_def)

    def start_jobs(self, options):
        """
        Loop on all scheduled jobs and send the START message to the slave.
        """
        # make the request atomic
        query = TestJob.objects.select_for_update()
        # Only select test job that are ready
        query = query.filter(state=TestJob.STATE_SCHEDULED)
        # exclude test job without a device: they are special test jobs like
        # dynamic connection.
        query = query.exclude(actual_device=None)
        # TODO: find a way to lock actual_device

        # Loop on all jobs
        for job in query:
            msg = None
            try:
                # Load job definition to get the variables for template
                # rendering
                job_def = yaml.load(job.definition)
                job_ctx = job_def.get('context', {})

                device = job.actual_device
                worker = device.worker_host

                # Load configurations
                env_str = load_optional_yaml_file(options['env'])
                env_dut_str = load_optional_yaml_file(options['env_dut'])
                device_cfg = device.load_configuration(job_ctx)
                dispatcher_cfg_file = os.path.join(options['dispatchers_config'],
                                                   "%s.yaml" % worker.hostname)
                dispatcher_cfg = load_optional_yaml_file(dispatcher_cfg_file)

                self.logger.info("[%d] START => %s (%s)", job.id,
                                 worker.hostname, device.hostname)
                self.controler.send_multipart([str(worker.hostname),
                                               'START', str(job.id),
                                               self.export_definition(job),
                                               str(device_cfg), dispatcher_cfg,
                                               env_str, env_dut_str])

                # For multinode jobs, start the dynamic connections
                parent = job
                for sub_job in job.sub_jobs_list:
                    if sub_job == parent or not sub_job.dynamic_connection:
                        continue

                    # inherit only enough configuration for dynamic_connection operation
                    self.logger.info("[%d] Trimming dynamic connection device configuration.", sub_job.id)
                    min_device_cfg = parent.actual_device.minimise_configuration(device_cfg)

                    self.logger.info("[%d] START => %s (connection)",
                                     sub_job.id, worker.hostname)
                    self.controler.send_multipart([str(worker.hostname),
                                                   'START', str(sub_job.id),
                                                   self.export_definition(sub_job),
                                                   yaml.dump(min_device_cfg), dispatcher_cfg,
                                                   env_str, env_dut_str])

            except jinja2.TemplateNotFound as exc:
                self.logger.error("[%d] Template not found: '%s'",
                                  job.id, exc.message)
                msg = "Infrastructure error: Template not found: '%s'" % \
                      exc.message
            except jinja2.TemplateSyntaxError as exc:
                self.logger.error("[%d] Template syntax error in '%s', line %d: %s",
                                  job.id, exc.name, exc.lineno, exc.message)
                msg = "Infrastructure error: Template syntax error in '%s', line %d: %s" % \
                      (exc.name, exc.lineno, exc.message)
            except IOError as exc:
                self.logger.error("[%d] Unable to read '%s': %s",
                                  job.id, exc.filename, exc.strerror)
                msg = "Infrastructure error: cannot open '%s': %s" % \
                      (exc.filename, exc.strerror)
            except yaml.YAMLError as exc:
                self.logger.error("[%d] Unable to parse job definition: %s",
                                  job.id, exc)
                msg = "Infrastructure error: cannot parse job definition: %s" % \
                      exc

            if msg:
                # TODO: do something with the error. Maybe setting lava.job result
                job.go_state_finished(TestJob.HEALTH_INCOMPLETE)
                job.save()

    def cancel_jobs(self):
        for job in TestJob.objects.filter(state=TestJob.STATE_CANCELING):
            worker = job.lookup_worker if job.dynamic_connection else job.actual_device.worker_host
            self.logger.info("[%d] CANCEL => %s", job.id,
                             worker.hostname)
            self.controler.send_multipart([str(worker.hostname),
                                           'CANCEL', str(job.id)])

    def handle(self, *args, **options):
        # Initialize logging.
        self.setup_logging("lava-master", options["level"],
                           options["log_file"], FORMAT)

        self.logger.info("[INIT] Dropping privileges")
        if not self.drop_privileges(options['user'], options['group']):
            self.logger.error("[INIT] Unable to drop privileges")
            return

        self.logger.info("[INIT] Marking all workers as offline")
        with transaction.atomic():
            for worker in Worker.objects.select_for_update().all():
                worker.go_state_offline()
                worker.save()

        auth = None
        # Create the sockets
        context = zmq.Context()
        self.controler = context.socket(zmq.ROUTER)

        if options['ipv6']:
            self.logger.info("[INIT] Enabling IPv6")
            self.controler.setsockopt(zmq.IPV6, 1)

        if options['encrypt']:
            self.logger.info("[INIT] Starting encryption")
            try:
                auth = ThreadAuthenticator(context)
                auth.start()
                self.logger.debug("[INIT] Opening master certificate: %s", options['master_cert'])
                master_public, master_secret = zmq.auth.load_certificate(options['master_cert'])
                self.logger.debug("[INIT] Using slaves certificates from: %s", options['slaves_certs'])
                auth.configure_curve(domain='*', location=options['slaves_certs'])
            except IOError as err:
                self.logger.error(err)
                auth.stop()
                return
            self.controler.curve_publickey = master_public
            self.controler.curve_secretkey = master_secret
            self.controler.curve_server = True

        self.controler.bind(options['master_socket'])

        # Poll on the sockets. This allow to have a
        # nice timeout along with polling.
        self.poller = zmq.Poller()
        self.poller.register(self.controler, zmq.POLLIN)

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
            self.logger.info("[CLOSE] Closing the controler socket and dropping messages")
            self.controler.close(linger=0)
            if options['encrypt']:
                auth.stop()
            context.term()

    def main_loop(self, options):
        last_schedule = last_dispatcher_check = time.time()

        while True:
            try:
                try:
                    # Compute the timeout
                    now = time.time()
                    timeout = min(SCHEDULE_INTERVAL - (now - last_schedule),
                                  PING_INTERVAL - (now - last_dispatcher_check))
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
                    while self.controler_socket():  # Unqueue all the pending messages
                        pass

                # Check dispatchers status
                now = time.time()
                if now - last_dispatcher_check > PING_INTERVAL:
                    for hostname, dispatcher in self.dispatchers.items():
                        if dispatcher.online and now - dispatcher.last_msg > DISPATCHER_TIMEOUT:
                            if hostname == "lava-logs":
                                self.logger.error("[STATE] lava-logs goes OFFLINE")
                            else:
                                self.logger.error("[STATE] Dispatcher <%s> goes OFFLINE", hostname)
                            self.dispatchers[hostname].go_offline()
                    last_dispatcher_check = now

                # Limit accesses to the database. This will also limit the rate of
                # CANCEL and START messages
                if time.time() - last_schedule > SCHEDULE_INTERVAL:
                    if self.dispatchers["lava-logs"].online:
                        schedule(self.logger)

                        # Dispatch scheduled jobs
                        with transaction.atomic():
                            self.start_jobs(options)
                    else:
                        self.logger.warning("lava-logs is offline: can't schedule jobs")

                    # Handle canceling jobs
                    self.cancel_jobs()

                    # Do not count the time taken to schedule jobs
                    last_schedule = time.time()

            except (OperationalError, InterfaceError):
                self.logger.info("[RESET] database connection reset.")
                # Closing the database connection will force Django to reopen
                # the connection
                connection.close()
