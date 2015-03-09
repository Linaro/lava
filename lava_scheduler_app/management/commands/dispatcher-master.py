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

import datetime
import errno
import fcntl
import jinja2
import logging
from optparse import make_option
import os
import signal
import time
import zmq

from django.core.management.base import BaseCommand
from django.db import transaction
from lava_scheduler_app.models import Device, TestJob

# pylint: disable=no-member,too-many-branches,too-many-statements,too-many-locals


# TODO constants to move into external files
FD_TIMEOUT = 60
TIMEOUT = 10
DB_LIMIT = 10

# TODO: share this value with dispatcher-slave
# This should be 3 times the slave ping timeout
DISPATCHER_TIMEOUT = 3 * 10


def mkdir(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


class SlaveDispatcher(object):  # pylint: disable=too-few-public-methods

    def __init__(self, hostname, online=False):
        self.hostname = hostname
        self.last_msg = time.time() if online else 0
        self.online = online

    def alive(self):
        self.last_msg = time.time()


class FileHandler(object):  # pylint: disable=too-few-public-methods

    def __init__(self, name, path):
        self.filename = name
        self.fd = open(path, 'a+')  # pylint: disable=invalid-name
        self.last_usage = time.time()

    def close(self):
        self.fd.close()


def create_job(job, device):
    # FIXME check the incoming device status
    job.actual_device = device
    device.current_job = job
    new_status = Device.RESERVED
    msg = "Reserved for job %s" % job.id
    device.state_transition_to(new_status, message=msg, job=job)
    device.status = new_status
    # Save the result
    job.save()
    device.save()


def start_job(job):
    job.status = TestJob.RUNNING
    # TODO: Only if that was not already the case !
    job.start_time = datetime.datetime.utcnow()
    device = job.actual_device
    msg = "Job %s running" % job.id
    new_status = Device.RUNNING
    device.state_transition_to(new_status, message=msg, job=job)
    device.status = new_status
    # Save the result
    job.save()
    device.save()


def end_job(job):
    # TODO: check if it has to be COMPLETE, INCOMPLETE or CANCELED
    job.status = TestJob.COMPLETE
    # TODO: Only if that was not already the case !
    job.end_time = datetime.datetime.utcnow()
    device = job.actual_device
    msg = "Job %s has ended" % job.id
    new_status = Device.IDLE
    device.state_transition_to(new_status, message=msg, job=job)
    device.status = new_status
    device.current_job = None
    # Save the result
    job.save()
    device.save()


def cancel_job(job):
    job.status = TestJob.CANCELED
    job.end_time = datetime.datetime.utcnow()
    device = job.actual_device
    msg = "Job %s cancelled" % job.id
    # TODO: what should be the new device status? health check should set
    # health unknown
    new_status = Device.IDLE
    device.state_transition_to(new_status, message=msg, job=job)
    device.status = new_status
    # Save the result
    job.save()
    device.save()


def send_status(hostname, socket, logger):
    """
    The master crashed, send a STATUS message to get the curren state of jobs
    """
    jobs = TestJob.objects.filter(actual_device__worker_host__hostname=hostname,
                                  is_pipeline=True,
                                  status=TestJob.RUNNING)
    for job in jobs:
        # TODO: keep track of the list of job to check (retrying)
        logger.info("STATUS %d => %s (%s)", job.id, hostname,
                    job.actual_device.hostname)
        socket.send_multipart([hostname, 'STATUS', str(job.id)])


class Command(BaseCommand):

    logger = None
    help = "LAVA dispatcher master"
    option_list = BaseCommand.option_list + (
        make_option('--master-socket',
                    default='tcp://*:5556',
                    help="Socket for master-slave communication"),
        make_option('--log-socket',
                    default='tcp://*:5555',
                    help="Socket waiting for logs"),
        make_option('-l', '--level',
                    default='DEBUG',
                    help="Logging level (ERROR, WARN, INFO, DEBUG)"),
        make_option('--templates',
                    default="/etc/lava-server/dispatcher-config/",
                    help="Base directory for device configuration templates"),
        # FIXME: ensure share/env.yaml is put into /etc/ by setup.py when merging.
        make_option('--env',
                    default="/etc/lava-server/dispatcher-config/env.yaml",
                    help="Environment variables for the dispatcher processes"),
        make_option('--output-dir',
                    default='/var/lib/lava-server/default/media/job-output',
                    help="Directory where to store job outputs"),
    )

    def handle(self, *args, **options):
        del logging.root.handlers[:]
        del logging.root.filters[:]
        # Create the logger
        FORMAT = '%(asctime)-15s %(levelname)s %(message)s'  # pylint: disable=invalid-name
        logging.basicConfig(format=FORMAT)
        self.logger = logging.getLogger('dispatcher-master')

        if options['level'] == 'ERROR':
            self.logger.setLevel(logging.ERROR)
        elif options['level'] == 'WARN':
            self.logger.setLevel(logging.WARN)
        elif options['level'] == 'INFO':
            self.logger.setLevel(logging.INFO)
        else:
            self.logger.setLevel(logging.DEBUG)

        # Create the sockets
        context = zmq.Context()
        pull_socket = context.socket(zmq.PULL)
        pull_socket.bind(options['log_socket'])
        controler = context.socket(zmq.ROUTER)
        controler.bind(options['master_socket'])

        # List of logs
        logs = {}
        # List of known dispatchers. At startup do not laod this from the
        # database. This will help to know if the slave as restarted or not.
        dispatchers = {}
        # Last access to the database for new jobs and cancelations
        last_db_access = 0

        # Poll on the sockets (only one for the moment). This allow to have a
        # nice timeout along with polling.
        poller = zmq.Poller()
        poller.register(pull_socket, zmq.POLLIN)
        poller.register(controler, zmq.POLLIN)

        # Mask signals and create a pipe that will receive a bit for each
        # signal received. Poll the pipe along with the zmq socket so that we
        # can only be interupted while reading data.
        (pipe_r, pipe_w) = os.pipe()
        flags = fcntl.fcntl(pipe_w, fcntl.F_GETFL, 0)
        fcntl.fcntl(pipe_w, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        signal.set_wakeup_fd(pipe_w)
        signal.signal(signal.SIGINT, lambda x, y: None)
        signal.signal(signal.SIGTERM, lambda x, y: None)
        signal.signal(signal.SIGQUIT, lambda x, y: None)
        poller.register(pipe_r, zmq.POLLIN)
        self.logger.info("[INIT] LAVA dispatcher-master has started.")

        while True:
            try:
                # TODO: Fix the timeout computation
                # Wait for data or a timeout
                sockets = dict(poller.poll(TIMEOUT * 1000))
            except zmq.error.ZMQError:
                continue

            if sockets.get(pipe_r) == zmq.POLLIN:
                self.logger.info("[POLL] Received a signal, leaving")
                break

            # Logging socket
            if sockets.get(pull_socket) == zmq.POLLIN:
                msg = pull_socket.recv_multipart()
                (job_id, filename, message) = msg

                # Clear filename
                filename = os.path.normpath(filename)
                if filename == '/':
                    self.logger.error("[%s] Wrong filename received, dropping the message", job_id)
                    continue
                filename = filename.lstrip('/')
                filename = "%s/job-%s/pipeline/%s" % (options['output_dir'],
                                                      job_id, filename)

                # Find the handler (if available)
                f_handler = None
                if job_id in logs:
                    if filename != logs[job_id].filename:
                        # Close the old file handler
                        logs[job_id].close()

                        path = os.path.join('/tmp', 'lava-dispatcher', 'jobs',
                                            job_id, filename)
                        mkdir(os.path.dirname(path))
                        logs[job_id] = FileHandler(filename, path)
                else:
                    self.logger.info("[%s] Receiving logs from a new job", job_id)
                    path = os.path.join('/tmp', 'lava-dispatcher', 'jobs',
                                        job_id, filename)
                    mkdir(os.path.dirname(path))
                    logs[job_id] = FileHandler(filename, path)

                # Mark the file handler as used
                # TODO: try to use a more pythonnic way
                logs[job_id].last_usage = time.time()

                # Write data
                self.logger.debug("[%s] %s -> %s", job_id, filename, message)
                f_handler = logs[job_id].fd
                f_handler.write(message)
                f_handler.write('\n')
                f_handler.flush()

                # FIXME: to be removed when the web UI knows how to deal with
                # pipeline logs
                filename = os.path.join(options['output_dir'],
                                        "job-%s" % job_id,
                                        'output.txt')
                with open(filename, 'a+') as f_out:
                    f_out.write(message)
                    f_out.write('\n')

            # Garbage collect file handlers
            now = time.time()
            for job_id in logs.keys():
                if now - logs[job_id].last_usage > FD_TIMEOUT:
                    self.logger.info("Collecting file handler '%s' from job %s",
                                     logs[job_id].filename, job_id)
                    logs[job_id].close()
                    del logs[job_id]

            # Command socket
            if sockets.get(controler) == zmq.POLLIN:
                msg = controler.recv_multipart()
                self.logger.debug("Receiving on controller: %s", msg)

                # 1: the hostname (see ZMQ documentation)
                hostname = msg[0]
                # 2: the action
                action = msg[1]
                # Handle the actions
                if action == 'HELLO':
                    self.logger.info("%s => HELLO", hostname)
                    controler.send_multipart([hostname, 'HELLO_OK'])
                    # If the dispatcher is known and sent an HELLO, means that
                    # the slave has restarted
                    if hostname in dispatchers:
                        self.logger.warning("Dispatcher <%s> has RESTARTED", hostname)
                    else:
                        self.logger.warning("New dispatcher %s", hostname)
                        dispatchers[hostname] = SlaveDispatcher(hostname, online=True)

                    # Mark the dispatcher as Online
                    # TODO: DB: mark the dispatcher as online in the database.
                    # For the moment this should not be done by this process as
                    # some dispatchers are using old and new dispatcher.

                    # Mark all jobs on this dispatcher as canceled.
                    # The dispatcher had (re)started, so all jobs have to be
                    # finished.
                    with transaction.atomic():
                        jobs = TestJob.objects.filter(actual_device__worker_host__hostname=hostname,
                                                      is_pipeline=True,
                                                      status=TestJob.RUNNING) \
                                              .select_for_update()
                        for job in jobs:
                            self.logger.info("Canceling job %d", job.id)
                            cancel_job(job)

                    # Mark the dispatcher as alive
                    dispatchers[hostname].alive()

                elif action == 'PING':
                    self.logger.debug("%s => PING", hostname)
                    # Send back a signal
                    controler.send_multipart([hostname, 'PONG'])

                    if hostname not in dispatchers:
                        # The server crashed: send a STATUS message
                        self.logger.warning("Unknown dispatcher %s (server crashed)", hostname)
                        dispatchers[hostname] = SlaveDispatcher(hostname, online=True)
                        send_status(hostname, controler, self.logger)

                    # Mark the dispatcher as alive
                    dispatchers[hostname].alive()

                elif action == 'END':
                    try:
                        job_id = int(msg[2])
                    except (IndexError, ValueError):
                        self.logger.error("Invalid message from <%s> '%s'", hostname, msg)
                        continue
                    self.logger.info("%s => END %d", hostname, job_id)
                    try:
                        with transaction.atomic():
                            job = TestJob.objects.select_for_update() \
                                                 .get(id=job_id)
                            end_job(job)
                    except TestJob.DoesNotExist:
                        self.logger.error("Unknown job %d", job_id)
                    # ACK even if the job is unknown to let the dispatcher
                    # forget about it
                    controler.send_multipart([hostname, 'END_OK', str(job_id)])

                    if hostname not in dispatchers:
                        # The server crashed: send a STATUS message
                        self.logger.warning("Unknown dispatcher %s (server crashed)", hostname)
                        dispatchers[hostname] = SlaveDispatcher(hostname, online=True)
                        send_status(hostname, controler, self.logger)

                    # Mark the dispatcher as alive
                    dispatchers[hostname].alive()

                elif action == 'START_OK':
                    try:
                        job_id = int(msg[2])
                    except (IndexError, ValueError):
                        self.logger.error("Invalid message from <%s> '%s'", hostname, msg)
                        continue
                    self.logger.info("%s => START_OK %d", hostname, job_id)
                    try:
                        with transaction.atomic():
                            job = TestJob.objects.select_for_update() \
                                                 .get(id=job_id)
                            start_job(job)
                    except TestJob.DoesNotExist:
                        self.logger.error("Unknown job <%d>", job_id)

                    if hostname not in dispatchers:
                        # The server crashed: send a STATUS message
                        self.logger.warning("Unknown dispatcher %s (server crashed)", hostname)
                        dispatchers[hostname] = SlaveDispatcher(hostname, online=True)
                        send_status(hostname, controler, self.logger)

                    # Mark the dispatcher as alive
                    dispatchers[hostname].alive()

                else:
                    self.logger.error("<%s> sent unknown action=%s, args=(%s)",
                                      hostname, action, msg[1:])

            # Check dispatchers status
            now = time.time()
            for hostname in dispatchers.keys():
                dispatcher = dispatchers[hostname]
                if dispatcher.online and now - dispatcher.last_msg > DISPATCHER_TIMEOUT:
                    self.logger.error("Dispatcher <%s> goes OFFLINE", hostname)
                    dispatchers[hostname].online = False
                    # TODO: DB: mark the dispatcher as offline and attached
                    # devices

            # Limit accesses to the database. This will also limit the rate of
            # CANCEL and START messages
            if now - last_db_access > DB_LIMIT:
                last_db_access = now
                # Dispatch jobs
                # TODO: make this atomic
                not_allocated = 0
                for job in TestJob.objects.filter(status=TestJob.SUBMITTED, is_pipeline=True):
                    if job.actual_device is None:
                        device = job.requested_device

                        # Launch the job
                        create_job(job, device)
                        self.logger.info("START %d => %s (%s)", job.id,
                                         device.worker_host.hostname, device.hostname)

                    else:
                        device = job.actual_device
                        self.logger.info("START %d => %s (%s) (retrying)", job.id,
                                         device.worker_host.hostname, device.hostname)
                    try:
                        # Load device configuration
                        device_configuration = device.load_device_configuration()

                        if os.path.exists(options['env']):
                            env = open(options['env'], 'r').read()

                        controler.send_multipart(
                            [str(job.actual_device.worker_host.hostname),
                             'START', str(job.id), str(job.definition),
                             str(device_configuration),
                             str(open(options['env'], 'r').read())])
                    # FIXME: add YAML.Error
                    except (jinja2.TemplateError, IOError) as exc:
                        if isinstance(exc, jinja2.TemplateNotFound):
                            self.logger.error("Template not found: '%s'", exc.message)
                            msg = "Infrastructure error: Template not found: '%s'" % \
                                  exc.message
                        elif isinstance(exc, jinja2.TemplateSyntaxError):
                            self.logger.error("Template syntax error in '%s', line %d: %s",
                                              exc.name, exc.lineno, exc.message)
                            msg = "Infrastructure error: Template syntax error in '%s', line %d: %s" % \
                                  (exc.name, exc.lineno, exc.message)
                        elif isinstance(exc, IOError):
                            self.logger.error("Unable to read '%s': %s",
                                              options['env'], exc.strerror)
                            msg = "Infrastructure error: cannot open '%s': %s" % \
                                  (options['env'], exc.strerror)
                        else:
                            self.logger.exception(exc)
                            msg = "Infrastructure error: %s" % exc.message

                        self.logger.error("Job %d is INCOMPLETE", job.id)
                        job.status = TestJob.INCOMPLETE
                        new_status = Device.IDLE
                        device.state_transition_to(
                            new_status,
                            message=msg,
                            job=job)
                        device.status = new_status
                        device.current_job = None
                        job.failure_comment = msg
                        job.save()
                        device.save()

                if not_allocated > 0:
                    self.logger.info("%d jobs not allocated yet", not_allocated)

                # Handle canceling jobs
                for job in TestJob.objects.filter(status=TestJob.CANCELING, is_pipeline=True):
                    self.logger.info("CANCEL %d => %s", job.id,
                                     job.actual_device.worker_host.hostname)
                    controler.send_multipart([str(job.actual_device.worker_host.hostname),
                                              'CANCEL', str(job.id)])

        # Closing sockets and droping messages.
        self.logger.info("Closing the socket and dropping messages")
        controler.close(linger=0)
        pull_socket.close(linger=0)
        context.term()
