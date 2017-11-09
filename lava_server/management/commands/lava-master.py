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
from django.db.models import Q
from django.db.utils import OperationalError, InterfaceError

from lava_scheduler_app.dbutils import (
    create_job, start_job,
    fail_job, cancel_job,
    parse_job_description,
    select_device,
)
from lava_scheduler_app.models import TestJob
from lava_scheduler_app.utils import mkdir
from lava_server.cmdutils import LAVADaemonCommand


# pylint: disable=no-member,too-many-branches,too-many-statements,too-many-locals

# Current version of the protocol
# The slave does send the protocol version along with the HELLO and HELLO_RETRY
# messages. If both version are not identical, the connection is refused by the
# master.
PROTOCOL_VERSION = 2
# TODO constants to move into external files
FD_TIMEOUT = 60
TIMEOUT = 10
DB_LIMIT = 10

# Slave ping interval and timeout
PING_INTERVAL = 20
DISPATCHER_TIMEOUT = 3 * PING_INTERVAL

# Log format
FORMAT = '%(asctime)-15s %(levelname)7s %(message)s'


class SlaveDispatcher(object):  # pylint: disable=too-few-public-methods

    def __init__(self, hostname, online=False):
        self.hostname = hostname
        self.last_msg = time.time() if online else 0
        self.online = online

    def alive(self):
        self.last_msg = time.time()


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
        self.dispatchers = {}

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
                                      status=TestJob.RUNNING)
        for job in jobs:
            self.logger.info("[%d] STATUS => %s (%s)", job.id, hostname,
                             job.actual_device.hostname)
            self.controler.send_multipart([hostname, 'STATUS', str(job.id)])

    def dispatcher_alive(self, hostname):
        if hostname not in self.dispatchers:
            # The server crashed: send a STATUS message
            self.logger.warning("Unknown dispatcher <%s> (server crashed)", hostname)
            self.dispatchers[hostname] = SlaveDispatcher(hostname, online=True)
            self.send_status(hostname)

        # Mark the dispatcher as alive
        self.dispatchers[hostname].alive()

    def controler_socket(self):
        msg = self.controler.recv_multipart()
        # This is way to verbose for production and should only be activated
        # by (and for) developers
        # self.logger.debug("[CC] Receiving: %s", msg)

        # 1: the hostname (see ZMQ documentation)
        hostname = msg[0]
        # 2: the action
        action = msg[1]
        # Handle the actions
        if action == 'HELLO' or action == 'HELLO_RETRY':
            self.logger.info("%s => %s", hostname, action)

            # Check the protocol version
            try:
                slave_version = int(msg[2])
            except (IndexError, ValueError):
                self.logger.error("Invalid message from <%s> '%s'", hostname, msg)
                return False
            if slave_version != PROTOCOL_VERSION:
                self.logger.error("<%s> using protocol v%d while master is using v%d",
                                  hostname, slave_version, PROTOCOL_VERSION)
                return False

            self.controler.send_multipart([hostname, 'HELLO_OK'])
            # If the dispatcher is known and sent an HELLO, means that
            # the slave has restarted
            if hostname in self.dispatchers:
                if action == 'HELLO':
                    self.logger.warning("Dispatcher <%s> has RESTARTED",
                                        hostname)
                else:
                    # Assume the HELLO command was received, and the
                    # action succeeded.
                    self.logger.warning("Dispatcher <%s> was not confirmed",
                                        hostname)
            else:
                # No dispatcher, treat HELLO and HELLO_RETRY as a normal HELLO
                # message.
                self.logger.warning("New dispatcher <%s>", hostname)
                self.dispatchers[hostname] = SlaveDispatcher(hostname, online=True)

            if action == 'HELLO':
                # FIXME: slaves need to be allowed to restart cleanly without affecting jobs
                # as well as handling unexpected crashes.
                self._cancel_slave_dispatcher_jobs(hostname)

            # Mark the dispatcher as alive
            self.dispatchers[hostname].alive()

        elif action == 'PING':
            self.logger.debug("%s => PING", hostname)
            # Send back a signal
            self.controler.send_multipart([hostname, 'PONG', str(PING_INTERVAL)])
            self.dispatcher_alive(hostname)

        elif action == 'END':
            try:
                job_id = int(msg[2])
                error_msg = msg[3]
                compressed_description = msg[4]
            except (IndexError, ValueError):
                self.logger.error("Invalid message from <%s> '%s'", hostname, msg)
                return False

            try:
                job = TestJob.objects.get(id=job_id)
            except TestJob.DoesNotExist:
                self.logger.error("[%d] Unknown job", job_id)
            else:
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
                            job = TestJob.objects.select_for_update().get(id=job_id)
                            if job.status == TestJob.CANCELING:
                                cancel_job(job)
                            fail_job(job, fail_msg=error_msg,
                                     job_status=TestJob.INCOMPLETE)

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

            # ACK even if the job is unknown to let the dispatcher
            # forget about it
            self.controler.send_multipart([hostname, 'END_OK', str(job_id)])
            self.dispatcher_alive(hostname)

        elif action == 'START_OK':
            try:
                job_id = int(msg[2])
            except (IndexError, ValueError):
                self.logger.error("Invalid message from <%s> '%s'", hostname, msg)
                return False
            self.logger.info("[%d] %s => START_OK", job_id, hostname)
            try:
                with transaction.atomic():
                    job = TestJob.objects.select_for_update() \
                                         .get(id=job_id)
                    start_job(job)
            except TestJob.DoesNotExist:
                self.logger.error("[%d] Unknown job", job_id)

            self.dispatcher_alive(hostname)

        else:
            self.logger.error("<%s> sent unknown action=%s, args=(%s)",
                              hostname, action, msg[1:])
        return True

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
            jobs = TestJob.objects.filter(
                actual_device__worker_host__hostname=hostname,
                is_pipeline=True,
                status=TestJob.RUNNING).select_for_update()

            for job in jobs:
                self.logger.info("[%d] Canceling", job.id)
                cancel_job(job)

    def export_definition(self, job):  # pylint: disable=no-self-use
        job_def = yaml.load(job.definition)
        job_def['compatibility'] = job.pipeline_compatibility

        # no need for the dispatcher to retain comments
        return yaml.dump(job_def)

    def process_jobs(self, options):
        for job in TestJob.objects.filter(
                Q(status=TestJob.SUBMITTED) & Q(is_pipeline=True) & ~Q(actual_device=None))\
                .order_by('-health_check', '-priority', 'submit_time', 'target_group', 'id'):
            device = None
            worker_host = None

            device = select_device(job, self.dispatchers)
            if not device:
                # e.g. one or more jobs in the MultiNode group do not yet have Reserved devices.
                continue
            # selecting device can change the job
            job.refresh_from_db()

            self.logger.info("[%d] Assigning %s device", job.id, device)
            if job.actual_device is None:
                # health checks
                device = job.requested_device
                if not device.worker_host:
                    msg = "Infrastructure error: Invalid worker information"
                    self.logger.error("[%d] %s", job.id, msg)
                    fail_job(job, msg, TestJob.INCOMPLETE)
                    continue
            # Launch the job
            create_job(job, device)
            self.logger.info("[%d] START => %s (%s)", job.id,
                             device.worker_host.hostname, device.hostname)
            worker_host = device.worker_host
            try:
                # Load job definition to get the variables for template
                # rendering
                job_def = yaml.load(job.definition)
                job_ctx = job_def.get('context', {})

                # Load env.yaml, env-dut.yaml and dispatcher configuration
                # All three are optional
                env_str = load_optional_yaml_file(options['env'])
                env_dut_str = load_optional_yaml_file(options['env_dut'])

                # Load device configuration
                if device:
                    device_configuration = device.load_configuration(job_ctx)
                    dispatcher_config_file = os.path.join(options['dispatchers_config'],
                                                          "%s.yaml" % worker_host.hostname)
                    dispatcher_config = load_optional_yaml_file(dispatcher_config_file)

                    self.controler.send_multipart(
                        [str(worker_host.hostname),
                         'START', str(job.id),
                         self.export_definition(job),
                         str(device_configuration),
                         dispatcher_config,
                         env_str, env_dut_str])

                if job.is_multinode:
                    # All secondary connections must be made from a dispatcher local to the one host device
                    # to allow for local firewalls etc. So the secondary connection is started on the
                    # remote worker of the "nominated" host.
                    # This job will not be a dynamic_connection, this is the parent.
                    device = None
                    device_configuration = None
                    # to get this far, the rest of the multinode group must also be ready
                    # so start the dynamic connections
                    parent = job

                    for group_job in job.sub_jobs_list:
                        if group_job == parent or not group_job.dynamic_connection:
                            continue

                        worker_host = parent.actual_device.worker_host
                        dispatcher_config_file = os.path.join(options['dispatchers_config'],
                                                              "%s.yaml" % worker_host.hostname)
                        dispatcher_config = load_optional_yaml_file(dispatcher_config_file)

                        # inherit only enough configuration for dynamic_connection operation
                        device_configuration = parent.actual_device.load_configuration(job_ctx)
                        self.logger.info("[%d] Trimming dynamic connection device configuration.", group_job.id)
                        device_configuration = parent.actual_device.minimise_configuration(device_configuration)

                        self.logger.info("[%d] START => %s (connection)", group_job.id, worker_host.hostname)
                        self.controler.send_multipart(
                            [str(worker_host.hostname),
                             'START', str(group_job.id),
                             self.export_definition(group_job),
                             str(device_configuration),
                             dispatcher_config,
                             env_str, env_dut_str])
                continue

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

            self.logger.error("[%d] INCOMPLETE job", job.id)
            fail_job(job=job, fail_msg=msg, job_status=TestJob.INCOMPLETE)

    def handle_canceling(self):
        for job in TestJob.objects.filter(status=TestJob.CANCELING, is_pipeline=True):
            worker_host = job.lookup_worker if job.dynamic_connection else job.actual_device.worker_host
            if not worker_host:
                self.logger.warning("[%d] Invalid worker information", job.id)
                # shouldn't happen
                fail_job(job, 'invalid worker information', TestJob.CANCELED)
                continue
            self.logger.info("[%d] CANCEL => %s", job.id,
                             worker_host.hostname)
            self.controler.send_multipart([str(worker_host.hostname),
                                           'CANCEL', str(job.id)])

    def handle(self, *args, **options):
        # Initialize logging.
        self.setup_logging("lava-master", options["level"],
                           options["log_file"], FORMAT)

        self.logger.info("Dropping privileges")
        if not self.drop_privileges(options['user'], options['group']):
            self.logger.error("Unable to drop privileges")
            return

        auth = None
        # Create the sockets
        context = zmq.Context()
        self.controler = context.socket(zmq.ROUTER)

        if options['ipv6']:
            self.logger.info("Enabling IPv6")
            self.controler.setsockopt(zmq.IPV6, 1)

        if options['encrypt']:
            self.logger.info("Starting encryption")
            try:
                auth = ThreadAuthenticator(context)
                auth.start()
                self.logger.debug("Opening master certificate: %s", options['master_cert'])
                master_public, master_secret = zmq.auth.load_certificate(options['master_cert'])
                self.logger.debug("Using slaves certificates from: %s", options['slaves_certs'])
                auth.configure_curve(domain='*', location=options['slaves_certs'])
            except IOError as err:
                self.logger.error(err)
                auth.stop()
                return
            self.controler.curve_publickey = master_public
            self.controler.curve_secretkey = master_secret
            self.controler.curve_server = True

        self.controler.bind(options['master_socket'])

        # Last access to the database for new jobs and cancelations
        last_db_access = 0

        # Poll on the sockets. This allow to have a
        # nice timeout along with polling.
        poller = zmq.Poller()
        poller.register(self.controler, zmq.POLLIN)

        # Translate signals into zmq messages
        (pipe_r, _) = self.setup_zmq_signal_handler()
        poller.register(pipe_r, zmq.POLLIN)

        self.logger.info("[INIT] LAVA master has started.")
        self.logger.info("[INIT] Using protocol version %d", PROTOCOL_VERSION)

        while True:
            try:
                try:
                    # TODO: Fix the timeout computation
                    # Wait for data or a timeout
                    sockets = dict(poller.poll(TIMEOUT * 1000))
                except zmq.error.ZMQError:
                    continue

                if sockets.get(pipe_r) == zmq.POLLIN:
                    self.logger.info("[POLL] Received a signal, leaving")
                    break

                # Command socket
                if sockets.get(self.controler) == zmq.POLLIN:
                    if not self.controler_socket():
                        continue

                # Check dispatchers status
                now = time.time()
                for hostname, dispatcher in self.dispatchers.iteritems():
                    if dispatcher.online and now - dispatcher.last_msg > DISPATCHER_TIMEOUT:
                        self.logger.error("[STATE] Dispatcher <%s> goes OFFLINE", hostname)
                        self.dispatchers[hostname].online = False
                        # TODO: DB: mark the dispatcher as offline and attached
                        # devices

                # Limit accesses to the database. This will also limit the rate of
                # CANCEL and START messages
                if now - last_db_access > DB_LIMIT:
                    last_db_access = now

                    # TODO: make this atomic
                    # Dispatch pipeline jobs with devices in Reserved state
                    self.process_jobs(options)

                    # Handle canceling jobs
                    self.handle_canceling()
            except (OperationalError, InterfaceError):
                self.logger.info("[RESET] database connection reset.")
                # Closing the database connection will force Django to reopen
                # the connection
                connection.close()

        # Drop controler socket: the protocol does handle lost messages
        self.logger.info("[CLOSE] Closing the controler socket and dropping messages")
        self.controler.close(linger=0)
        if options['encrypt']:
            auth.stop()
        context.term()
