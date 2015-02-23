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
import logging
from optparse import make_option
import os
import time
import zmq

from django.core.management.base import BaseCommand
from django.db import transaction
from lava_scheduler_app.models import Device, TestJob, Worker


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


class SlaveDispatcher(object):
    def __init__(self, hostname, online=False):
        self.hostname = hostname
        self.last_msg = time.time() if online else 0
        self.online = online

    def alive(self):
        self.last_msg = time.time()


class FileHandler(object):
    def __init__(self, name, path):
        self.filename = name
        self.fd = open(path, 'w+')
        self.last_usage = time.time()

    def close(self):
        self.fd.close()


def create_job(job, device):
    job.actual_device = device
    device.current_job = job
    # TODO: create transition state
    device.status = Device.RESERVED
    # Save the result
    job.save()
    device.save()


def start_job(job):
    job.status = TestJob.RUNNING
    # TODO: Only if that was not already the case !
    job.start_time = datetime.datetime.utcnow()
    device = job.actual_device
    # TODO: create transition state
    device.status = Device.RUNNING
    # Save the result
    job.save()
    device.save()


def end_job(job):
    # TODO: check if it has to be COMPLETE, INCOMPLETE or CANCELED
    job.status = TestJob.COMPLETE
    # TODO: Only if that was not already the case !
    job.end_time = datetime.datetime.utcnow()
    device = job.actual_device
    # TODO: create transition state
    device.status = Device.IDLE
    # Save the result
    job.save()
    device.save()


def cancel_job(job):
    job.status = TestJob.CANCELED
    job.end_time = datetime.datetime.utcnow()
    device = job.actual_device
    # TODO: create transition state
    # TODO: what should be the new device status?
    device.status = Device.IDLE
    # Save the result
    job.save()
    device.save()


def send_status(hostname, socket, logger):
    # The master crashed, send a signal to get the status of each job
    jobs = TestJob.objects.filter(actual_device__worker_host__hostname=hostname,
                                  is_pipeline=True,
                                  status=TestJob.RUNNING)
    for job in jobs:
        # TODO: keep track of the list of job to check (retrying)
        logger.info("STATUS %d => %s", job.id, hostname)
        socket.send_multipart([hostname, 'STATUS', str(job.id)])


class Command(BaseCommand):

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
    )

    def handle(self, *args, **options):
        # Create the logger
        FORMAT = '%(asctime)-15s %(levelname)s [%(job_id)s] %(message)s'
        extra = {'job_id': 'Server'}
        logging.basicConfig(format=FORMAT)
        logger = logging.getLogger('dispatcher-master')

        if options['level'] == 'ERROR':
            logger.setLevel(logging.ERROR)
        elif options['level'] == 'WARN':
            logger.setLevel(logging.WARN)
        elif options['level'] == 'INFO':
            logger.setLevel(logging.INFO)
        else:
            logger.setLevel(logging.DEBUG)

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

        # Poll on the sockets (only one for the moment). This allow to have a nice
        # timeout along with polling.
        poller = zmq.Poller()
        poller.register(pull_socket, zmq.POLLIN)
        poller.register(controler, zmq.POLLIN)

        while True:
            try:
                # TODO: Fix the timeout computation
                # Wait for data or a timeout
                sockets = dict(poller.poll(TIMEOUT * 1000))
            except KeyboardInterrupt:
                logger.info("Signal received, leaving", extra=extra)
                # Close sockets on Ctr+C
                # TODO: add a way to dump data anyway and then leave
                pull_socket.close()
                break

            # Logging socket
            if sockets.get(pull_socket) == zmq.POLLIN:
                msg = pull_socket.recv_multipart()
                (job_id, filename, message) = msg

                # Clear filename
                filename = os.path.realpath(filename)
                if filename == '/':
                    logger.error("Wrong filename received, dropping the message",
                                 extra={'job_id': job_id})
                    continue
                filename = filename[1:]
                # TODO: check that the path has the righ prefix

                # Find the handler (if available)
                f_handler = None
                if job_id in logs:
                    if filename != logs[job_id].filename:
                        # Close the old file handler
                        logs[job_id].close()

                        path = os.path.join('/tmp', 'lava-dispatcher', 'jobs', job_id, filename)
                        mkdir(os.path.dirname(path))
                        logs[job_id] = FileHandler(filename, path)
                else:
                    logger.info("Receiving logs from a new job", extra={'job_id': job_id})
                    path = os.path.join('/tmp', 'lava-dispatcher', 'jobs', job_id, filename)
                    mkdir(os.path.dirname(path))
                    logs[job_id] = FileHandler(filename, path)

                # Mark the file handler as used
                # TODO: try to use a more pythonnic way
                logs[job_id].last_usage = time.time()

                # Write data
                logger.debug("%s -> %s", filename, message, extra={'job_id': job_id})
                f_handler = logs[job_id].fd
                f_handler.write(message)
                f_handler.write('\n')
                f_handler.flush()

            # Garbage collect file handlers
            now = time.time()
            for job_id in logs.keys():
                if now - logs[job_id].last_usage > FD_TIMEOUT:
                    logger.info("Collecting file handler '%s' from job %s",
                                logs[job_id].filename, job_id,
                                extra={'job_id': 'Server'})
                    logs[job_id].close()
                    del logs[job_id]

            # Command socket
            if sockets.get(controler) == zmq.POLLIN:
                msg = controler.recv_multipart()
                logger.debug("Receiving on controler: %s", msg, extra=extra)

                # 1: the hostname (see ZMQ documentation)
                hostname = msg[0]
                # 2: the action
                action = msg[1]
                # Handle the actions
                if action == 'HELLO':
                    logger.info("%s => HELLO", hostname, extra=extra)
                    controler.send_multipart([hostname, 'HELLO_OK'])
                    # If the dispatcher is known and sent an HELLO, means that the
                    # slave has restarted
                    if hostname in dispatchers:
                        logger.warning("Dispatcher <%s> has RESTARTED", hostname, extra=extra)
                    else:
                        logger.warning("New dispatcher %s", hostname, extra=extra)
                        dispatchers[hostname] = SlaveDispatcher(hostname, online=True)

                    # Mark the dispatcher as Online
                    # TODO: DB: mark the dispatcher as online in the
                    # database. For the moment this should not be done by
                    # this process as some dispatchers are using old and
                    # new dispatcher.

                    # Mark all jobs on this dispatcher as canceled.
                    # The dispatcher had (re)started, so all jobs have to be finished.
                    with transaction.atomic():
                        jobs = TestJob.objects.filter(actual_device__worker_host__hostname=hostname,
                                                      is_pipeline=True,
                                                      status=TestJob.RUNNING) \
                                              .select_for_update()
                        for job in jobs:
                            logger.info("Canceling job %d", job.id)
                            cancel_job(job)

                    # Mark the dispatcher as alive
                    dispatchers[hostname].alive()

                elif action == 'PING':
                    logger.debug("%s => PING", hostname, extra=extra)
                    # Send back a signal
                    controler.send_multipart([hostname, 'PONG'])

                    if hostname not in dispatchers:
                        # The server crashed: send a STATUS message
                        logger.warning("Unknown dispatcher %s (server crashed)", hostname, extra=extra)
                        dispatchers[hostname] = SlaveDispatcher(hostname, online=True)
                        send_status(hostname, controler, logger)

                    # Mark the dispatcher as alive
                    dispatchers[hostname].alive()

                elif action == 'END':
                    try:
                        job_id = int(msg[2])
                    except (IndexError, ValueError):
                        logger.error("Invalid message from <%s> '%s'", hostname, msg, extra=extra)
                        continue
                    logger.info("%s => END %d", hostname, job_id, extra=extra)
                    try:
                        with transaction.atomic():
                            job = TestJob.objects.select_for_update() \
                                                 .get(id=job_id)
                            end_job(job)
                    except TestJob.DoesNotExist:
                        logger.error("Unknown job %d", job_id)
                    # ACK even if the job is unknown to let the dispatcher
                    # forget about it
                    controler.send_multipart([hostname, 'END_OK', str(job_id)])

                    if hostname not in dispatchers:
                        # The server crashed: send a STATUS message
                        logger.warning("Unknown dispatcher %s (server crashed)", hostname, extra=extra)
                        dispatchers[hostname] = SlaveDispatcher(hostname, online=True)
                        send_status(hostname, controler, logger)

                    # Mark the dispatcher as alive
                    dispatchers[hostname].alive()

                elif action == 'START_OK':
                    try:
                        job_id = int(msg[2])
                    except (IndexError, ValueError):
                        logger.error("Invalid message from <%s> '%s'", hostname, msg, extra=extra)
                        continue
                    logger.info("%s => START_OK %d", hostname, job_id, extra=extra)
                    try:
                        with transaction.atomic():
                            job = TestJob.objects.select_for_update() \
                                                 .get(id=job_id)
                            start_job(job)
                    except TestJob.DoesNotExist:
                        logger.error("Unknown job <%d>", job_id)

                    if hostname not in dispatchers:
                        # The server crashed: send a STATUS message
                        logger.warning("Unknown dispatcher %s (server crashed)", hostname, extra=extra)
                        dispatchers[hostname] = SlaveDispatcher(hostname, online=True)
                        send_status(hostname, controler, logger)

                    # Mark the dispatcher as alive
                    dispatchers[hostname].alive()

                else:
                    logger.error("<%s> sent unknown action=%s, args=(%s)",
                                 hostname, action, msg[1:], extra=extra)

            # Check dispatchers status
            now = time.time()
            for hostname in dispatchers.keys():
                dispatcher = dispatchers[hostname]
                if dispatcher.online and now - dispatcher.last_msg > DISPATCHER_TIMEOUT:
                    logger.error("Dispatcher <%s> goes OFFLINE", hostname, extra=extra)
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
                devices = Device.objects.filter(status=Device.IDLE, is_pipeline=True)
                for job in TestJob.objects.filter(status=TestJob.SUBMITTED, is_pipeline=True):
                    if job.actual_device is None:
                        device_type = job.requested_device_type
                        try:
                            # Choose a random matching device
                            device = devices.filter(device_type=device_type).order_by('?')[0]
                        except IndexError:
                            logger.debug("Job <%d> (%s for %s) not allocated yet", job.id,
                                         job.description, job.requested_device_type)
                            not_allocated += 1
                            continue

                        # Launch the job
                        create_job(job, device)
                        logger.info("START %d => %s (%s)", job.id,
                                    device.worker_host.hostname, device.hostname)
                        controler.send_multipart([str(device.worker_host.hostname), 'START',
                                                  str(job.id),
                                                  str(job.definition), 'TODO'])

                    else:
                        device = job.actual_device
                        logger.info("START %d => %s (%s) (retrying)", job.id,
                                    device.worker_host.hostname, device.hostname)
                        controler.send_multipart([str(job.actual_device.worker_host.hostname), 'START',
                                                  str(job.id),
                                                  str(job.definition), 'TODO'])

                if not_allocated > 0:
                    logger.info("%d jobs not allocated yet", not_allocated)

                # Handle canceling jobs
                for job in TestJob.objects.filter(status=TestJob.CANCELING, is_pipeline=True):
                    logger.info("CANCEL %d => %s", job.id, job.actual_device.worker_host.hostname)
                    controler.send_multipart([str(job.actual_device.worker_host.hostname),
                                              'CANCEL', str(job.id)])
