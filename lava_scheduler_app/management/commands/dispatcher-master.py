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

import errno
import fcntl
import jinja2
import logging
from optparse import make_option
import os
import signal
import time
import yaml
import zmq

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from lava_scheduler_app.models import Device, TestJob, JobPipeline
from lava_results_app.models import TestSuite
from lava_results_app.dbutils import map_scanned_results, map_metadata
from lava_dispatcher.pipeline.device import PipelineDevice
from lava_dispatcher.pipeline.parser import JobParser
from lava_dispatcher.pipeline.action import JobError


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
    job.start_time = timezone.now()
    device = job.actual_device
    msg = "Job %s running" % job.id
    new_status = Device.RUNNING
    job.save()
    if not job.dynamic_connection:
        device.state_transition_to(new_status, message=msg, job=job)
        device.status = new_status
        # Save the result
        device.save()


def fail_job(job, fail_msg=None, job_status=TestJob.INCOMPLETE):
    """
    Fail the job due to issues which would compromise any other jobs
    in the same multinode group.
    If not multinode, simply wraps end_job.
    """
    if not job.is_multinode:
        end_job(job, fail_msg=fail_msg, job_status=job_status)
        return
    for failed_job in job.sub_jobs_list:
        end_job(failed_job, fail_msg=fail_msg, job_status=job_status)


def end_job(job, fail_msg=None, job_status=TestJob.COMPLETE):
    """
    Controls the end of a single job..
    If the job failed rather than simply ended with an exit code, use fail_job.
    """
    if job.status in [TestJob.COMPLETE, TestJob.INCOMPLETE, TestJob.CANCELED]:
        # testjob has already ended and been marked as such
        return
    job.status = job_status
    if job.status == TestJob.CANCELING:
        job.status = TestJob.CANCELED
    if job.start_time and not job.end_time:
        job.end_time = timezone.now()
    device = job.actual_device
    if fail_msg:
        job.failure_comment = "%s %s" % (job.failure_comment, fail_msg) if job.failure_comment else fail_msg
    if not device:
        job.save()
        return
    msg = "Job %s has ended. Setting %s" % (job.id, TestJob.STATUS_CHOICES[job.status])
    new_status = Device.IDLE
    device.state_transition_to(new_status, message=msg, job=job)
    device.status = new_status
    device.current_job = None
    # Save the result
    job.save()
    device.save()


def cancel_job(job):
    job.status = TestJob.CANCELED
    job.end_time = timezone.now()
    if job.dynamic_connection:
        job.save()
        return
    device = job.actual_device
    msg = "Job %s cancelled" % job.id
    # TODO: what should be the new device status? health check should set
    # health unknown
    new_status = Device.IDLE
    device.state_transition_to(new_status, message=msg, job=job)
    device.status = new_status
    if device.current_job and device.current_job == job:
        device.current_job = None
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
        logger.info("[%d] STATUS => %s (%s)", job.id, hostname,
                    job.actual_device.hostname)
        socket.send_multipart([hostname, 'STATUS', str(job.id)])


def select_device(job):
    """
    Transitioning a device from Idle to Reserved is the responsibility of the scheduler_daemon (currently).
    This function just checks that the reserved device is valid for this job.
    Jobs will only enter this function if a device is already reserved for that job.
    Stores the pipeline description

    To prevent cycling between lava_scheduler_daemon:assign_jobs and here, if a job
    fails validation, the job is incomplete. Issues with this need to be fixed using
    device tags.
    """
    logger = logging.getLogger('dispatcher-master')
    if not job.dynamic_connection:
        if not job.actual_device:
            return None
        if job.actual_device.status is not Device.RESERVED:
            # should not happen
            logger.error("[%d] device [%s] not in reserved state", job.id, job.actual_device)
            return None

        if job.actual_device.worker_host is None:
            fail_msg = "Misconfigured device configuration for %s - missing worker_host" % job.actual_device
            fail_job(job, fail_msg=fail_msg)
            logger.error(fail_msg)

    if job.is_multinode:
        # inject the actual group hostnames into the roles for the dispatcher to populate in the overlay.
        devices = {}
        for multinode_job in job.sub_jobs_list:
            # build a list of all devices in this group
            definition = yaml.load(multinode_job.definition)
            # devices are not necessarily assigned to all jobs in a group at the same time
            # check all jobs in this multinode group before allowing any to start.
            if multinode_job.dynamic_connection:
                logger.debug("[%s] dynamic connection job", multinode_job.sub_id)
                continue
            if not multinode_job.actual_device:
                logger.debug("[%s] job has no device yet", multinode_job.sub_id)
                return None
            devices[str(multinode_job.actual_device.hostname)] = definition['protocols']['lava-multinode']['role']
        for multinode_job in job.sub_jobs_list:
            # apply the complete list to all jobs in this group
            definition = yaml.load(multinode_job.definition)
            definition['protocols']['lava-multinode']['roles'] = devices
            multinode_job.definition = yaml.dump(definition)
            multinode_job.save()

    # Load job definition to get the variables for template rendering
    job_def = yaml.load(job.definition)
    job_ctx = job_def.get('context', {})
    parser = JobParser()
    device = None
    device_object = None
    if not job.dynamic_connection:
        device = job.actual_device

        try:
            device_config = device.load_device_configuration(job_ctx)  # raw dict
        except (jinja2.TemplateError, yaml.YAMLError, IOError) as exc:
            # FIXME: report the exceptions as useful user messages
            logger.error("[%d] jinja2 error: %s" % (job.id, exc))
            return None
        if not device_config or type(device_config) is not dict:
            # it is an error to have a pipeline device without a device dictionary as it will never get any jobs.
            msg = "Administrative error. Device '%s' has no device dictionary." % device.hostname
            logger.error('[%d] device-dictionary error: %s' % (job.id, msg))
            # as we don't control the scheduler, yet, this has to be an error and an incomplete job.
            # the scheduler_daemon sorts by a fixed order, so this would otherwise just keep on repeating.
            fail_job(job, fail_msg=msg)
            return None

        device_object = PipelineDevice(device_config, device.hostname)  # equivalent of the NewDevice in lava-dispatcher, without .yaml file.
        # FIXME: drop this nasty hack once 'target' is dropped as a parameter
        if 'target' not in device_object:
            device_object.target = device.hostname
        device_object['hostname'] = device.hostname

    validate_list = job.sub_jobs_list if job.is_multinode else [job]
    for check_job in validate_list:
        parser_device = None if job.dynamic_connection else device_object
        try:
            logger.debug("[%d] parsing definition" % check_job.id)
            # pass (unused) output_dir just for validation as there is no zmq socket either.
            pipeline_job = parser.parse(
                check_job.definition, parser_device,
                check_job.id, None, output_dir=check_job.output_dir)
        except (AttributeError, JobError, NotImplementedError, KeyError, TypeError) as exc:
            logger.error('[%d] parser error: %s' % (check_job.id, exc))
            fail_job(check_job, fail_msg=exc)
            return None
        try:
            logger.debug("[%d] validating actions" % check_job.id)
            pipeline_job.pipeline.validate_actions()
        except (AttributeError, JobError, KeyError, TypeError) as exc:
            logger.error({device: exc})
            fail_job(check_job, fail_msg=exc)
            return None
        if pipeline_job:
            pipeline = pipeline_job.describe()
            # write the pipeline description to the job output directory.
            if not os.path.exists(check_job.output_dir):
                os.makedirs(check_job.output_dir)
            with open(os.path.join(check_job.output_dir, 'description.yaml'), 'w') as describe_yaml:
                describe_yaml.write(yaml.dump(pipeline))
            map_metadata(yaml.dump(pipeline), job)
    return device


def get_env_string(filename):
    """
    Returns the string after checking for YAML errors which would cause issues later.
    """
    if not os.path.exists(filename):
        return ''
    logger = logging.getLogger('dispatcher-master')
    env_str = str(open(filename, 'r').read())
    try:
        yaml.load(env_str)
    except yaml.ScannerError as exc:
        logger.exception("%s is not valid YAML (%s) - skipping" % (filename, exc))
        env_str = ''
    return env_str


class Command(BaseCommand):
    """
    worker_host is the hostname of the worker - under the old dispatcher, this was declared by
    that worker using the heartbeat. In the new dispatcher, this field is set by the admin
    and could therefore be empty in a misconfigured instance.
    """
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
                    default="/etc/lava-server/env.yaml",
                    help="Environment variables for the dispatcher processes"),
        make_option('--env-dut',
                    default="/etc/lava-server/env.dut.yaml",
                    help="Environment variables for device under test"),
        make_option('--output-dir',
                    default='/var/lib/lava-server/default/media/job-output',
                    help="Directory where to store job outputs"),
    )

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

    def handle(self, *args, **options):
        # FIXME: this function is getting much too long and complex.
        del logging.root.handlers[:]
        del logging.root.filters[:]
        # Create the logger
        FORMAT = '%(asctime)-15s %(levelname)s %(message)s'  # pylint: disable=invalid-name
        logging.basicConfig(format=FORMAT, filename='/var/log/lava-server/lava-master.log')
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
                try:
                    (job_id, level, name, message) = msg
                except ValueError:
                    # do not let a bad message stop the master.
                    self.logger.error("Failed to parse log message, skipping: %s", msg)
                    continue

                try:
                    scanned = yaml.load(message)
                except yaml.YAMLError:
                    # failure to scan is not an error here, it just means the message is not a result
                    scanned = None
                # the results logger wraps the OrderedDict in a dict called results, for identification,
                # YAML then puts that into a list of one item for each call to log.results.
                if type(scanned) is list and len(scanned) == 1:
                    if type(scanned[0]) is dict and 'results' in scanned[0]:
                        job = TestJob.objects.get(id=job_id)
                        ret = map_scanned_results(scanned_dict=scanned[0], job=job)
                        if not ret:
                            self.logger.warning("[%s] Unable to map scanned results: %s" % (job_id, yaml.dump(scanned[0])))

                # Clear filename
                if '/' in level or '/' in name:
                    self.logger.error("[%s] Wrong level or name received, dropping the message", job_id)
                    continue
                filename = "%s/job-%s/pipeline/%s/%s-%s.log" % (options['output_dir'],
                                                                job_id, level.split('.')[0],
                                                                level, name)

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

                # n.b. logging here would produce a log entry for every message in every job.

                # Write data
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
                    self.logger.info("[%s] Collecting file handler '%s'",
                                     job_id, logs[job_id].filename)
                    logs[job_id].close()
                    del logs[job_id]

            # Command socket
            if sockets.get(controler) == zmq.POLLIN:
                msg = controler.recv_multipart()
                self.logger.debug("[CC] Receiving: %s", msg)

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
                        self.logger.warning("New dispatcher <%s>", hostname)
                        dispatchers[hostname] = SlaveDispatcher(hostname, online=True)

                    self._cancel_slave_dispatcher_jobs(hostname)

                    # Mark the dispatcher as alive
                    dispatchers[hostname].alive()

                elif action == "HELLO_RETRY":
                    self.logger.info("%s => HELLO_RETRY", hostname)
                    controler.send_multipart([hostname, "HELLO_OK"])

                    if hostname in dispatchers:
                        # Assume the HELLO command was received, and the
                        # action succeeded.
                        self.logger.warning(
                            "Dispatcher <%s> was not confirmed", hostname)
                    else:
                        # No dispatcher, treat it as a normal HELLO message.
                        self.logger.warning("New dispatcher <%s>", hostname)
                        dispatchers[hostname] = SlaveDispatcher(
                            hostname, online=True)

                        self._cancel_slave_dispatcher_jobs(hostname)

                    # Mark the dispatcher as alive
                    dispatchers[hostname].alive()

                elif action == 'PING':
                    self.logger.debug("%s => PING", hostname)
                    # Send back a signal
                    controler.send_multipart([hostname, 'PONG'])

                    if hostname not in dispatchers:
                        # The server crashed: send a STATUS message
                        self.logger.warning("Unknown dispatcher <%s> (server crashed)", hostname)
                        dispatchers[hostname] = SlaveDispatcher(hostname, online=True)
                        send_status(hostname, controler, self.logger)

                    # Mark the dispatcher as alive
                    dispatchers[hostname].alive()

                elif action == 'END':
                    status = TestJob.COMPLETE
                    try:
                        job_id = int(msg[2])
                        job_status = int(msg[3])
                    except (IndexError, ValueError):
                        self.logger.error("Invalid message from <%s> '%s'", hostname, msg)
                        continue
                    if job_status:
                        self.logger.info("[%d] %s => END with error %d", job_id, hostname, job_status)
                        status = TestJob.INCOMPLETE
                    else:
                        self.logger.info("[%d] %s => END", job_id, hostname)
                    try:
                        with transaction.atomic():
                            job = TestJob.objects.select_for_update() \
                                                 .get(id=job_id)
                            if job.status == TestJob.CANCELING:
                                cancel_job(job)
                            else:
                                end_job(job, job_status=status)
                    except TestJob.DoesNotExist:
                        self.logger.error("[%d] Unknown job", job_id)
                    # ACK even if the job is unknown to let the dispatcher
                    # forget about it
                    controler.send_multipart([hostname, 'END_OK', str(job_id)])

                    if hostname not in dispatchers:
                        # The server crashed: send a STATUS message
                        self.logger.warning("Unknown dispatcher <%s> (server crashed)", hostname)
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
                    self.logger.info("[%d] %s => START_OK", job_id, hostname)
                    try:
                        with transaction.atomic():
                            job = TestJob.objects.select_for_update() \
                                                 .get(id=job_id)
                            start_job(job)
                    except TestJob.DoesNotExist:
                        self.logger.error("[%d] Unknown job", job_id)

                    if hostname not in dispatchers:
                        # The server crashed: send a STATUS message
                        self.logger.warning("Unknown dispatcher <%s> (server crashed)", hostname)
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
                # only pick up pipeline jobs with devices in Reserved state
                for job in TestJob.objects.filter(
                        status=TestJob.SUBMITTED,
                        is_pipeline=True,
                        actual_device__isnull=False).order_by(
                            '-health_check', '-priority', 'submit_time', 'target_group', 'id'):
                    if job.dynamic_connection:
                        # A secondary connection must be made from a dispatcher local to the host device
                        # to allow for local firewalls etc. So the secondary connection is started on the
                        # remote worker of the "nominated" host.
                        # FIXME:
                        worker_host = job.lookup_worker
                        self.logger.info("[%d] START => %s (connection)", job.id,
                                         worker_host.hostname)
                    else:
                        device = select_device(job)
                        if not device:
                            continue
                        # selecting device can change the job
                        job = TestJob.objects.get(id=job.id)
                        self.logger.info("[%d] Assigning %s device", job.id, device)
                        if job.actual_device is None:
                            device = job.requested_device

                            # Launch the job
                            create_job(job, device)
                            self.logger.info("[%d] START => %s (%s)", job.id,
                                             device.worker_host.hostname, device.hostname)
                            worker_host = device.worker_host
                        else:
                            device = job.actual_device
                            self.logger.info("[%d] START => %s (%s) (retrying)", job.id,
                                             device.worker_host.hostname, device.hostname)
                            worker_host = device.worker_host
                    try:
                        # Load job definition to get the variables for template
                        # rendering
                        job_def = yaml.load(job.definition)
                        job_ctx = job_def.get('context', {})

                        # Load device configuration
                        device_configuration = None \
                            if job.dynamic_connection else device.load_device_configuration(job_ctx)

                        if job.is_multinode:
                            for group_job in job.sub_jobs_list:
                                if group_job.dynamic_connection:
                                    # to get this far, the rest of the multinode group must also be ready
                                    # so start the dynamic connections
                                    # FIXME: rationalise and streamline
                                    controler.send_multipart(
                                        [str(worker_host.hostname),
                                         'START', str(group_job.id), str(group_job.definition),
                                         str(device_configuration),
                                         str(open(options['env'], 'r').read())])

                        controler.send_multipart(
                            [str(worker_host.hostname),
                             'START', str(job.id), str(job.definition),
                             str(device_configuration),
                             get_env_string(options['env']), get_env_string(options['env_dut'])])

                    except (jinja2.TemplateError, IOError, yaml.YAMLError) as exc:
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
                        elif isinstance(exc, yaml.YAMLError):
                            self.logger.error("Unable to parse job definition: %s",
                                              exc)
                            msg = "Infrastructure error: cannot parse job definition: %s" % \
                                  exc
                        else:
                            self.logger.exception(exc)
                            msg = "Infrastructure error: %s" % exc.message

                        self.logger.error("[%d] INCOMPLETE job", job.id)
                        job.status = TestJob.INCOMPLETE
                        if job.dynamic_connection:
                            job.failure_comment = msg
                            job.save()
                        else:
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
                    worker_host = job.lookup_worker if job.dynamic_connection else job.actual_device.worker_host
                    if not worker_host:
                        self.logger.warning("[%d] Invalid worker information" % job.id)
                        # shouldn't happen
                        fail_job(job, 'invalid worker information', TestJob.CANCELED)
                        continue
                    self.logger.info("[%d] CANCEL => %s", job.id,
                                     worker_host.hostname)
                    controler.send_multipart([str(worker_host.hostname),
                                              'CANCEL', str(job.id)])

        # Closing sockets and droping messages.
        self.logger.info("Closing the socket and dropping messages")
        controler.close(linger=0)
        pull_socket.close(linger=0)
        context.term()
