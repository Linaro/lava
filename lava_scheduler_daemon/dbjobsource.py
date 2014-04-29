import datetime
import logging
import os
import shutil
import urlparse
import copy
import socket

from dashboard_app.models import Bundle

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import connection
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.utils import DatabaseError

from linaro_django_xmlrpc.models import AuthToken
from psycopg2.extensions import TransactionRollbackError
import simplejson

from twisted.internet.threads import deferToThread

from zope.interface import implements

import lava_dispatcher.config as dispatcher_config

from lava_scheduler_app.models import (
    Device,
    TestJob,
    TemporaryDevice,
)
from lava_scheduler_app import utils
from lava_scheduler_daemon.worker import WorkerData
from lava_scheduler_daemon.jobsource import IJobSource
import signal
import platform

try:
    from psycopg2 import InterfaceError, OperationalError
except ImportError:
    class InterfaceError(Exception):
        pass

    class OperationalError(Exception):
        pass


def find_device_for_job(job, device_list):
    """
    If the device has the same tags as the job or all the tags required
    for the job and some others which the job does not explicitly specify,
    check if this device be assigned to this job for this user.
    """
    if job.health_check is True:
        if job.requested_device.status == Device.OFFLINE:
            return job.requested_device
    for device in device_list:
        if device == job.requested_device:
            if device.can_submit(job.submitter) and\
                    set(job.tags.all()) & set(device.tags.all()) == set(job.tags.all()):
                return device
    for device in device_list:
        if device.device_type == job.requested_device_type:
            if device.can_submit(job.submitter) and\
                    set(job.tags.all()) & set(device.tags.all()) == set(job.tags.all()):
                return device
    return None


def get_configured_devices():
    return dispatcher_config.list_devices()


def get_temporary_devices(devices):
    tmp_device_list = set()
    for dev in devices:
        try:
            device = Device.objects.get(hostname=dev)
            if device.current_job and device.current_job.vm_group:
                vm_group = device.current_job.vm_group
                tmp_devices = TemporaryDevice.objects.filter(vm_group=vm_group)
                for tmp_dev in tmp_devices:
                    tmp_device_list.add(tmp_dev.hostname)
        except Device.DoesNotExist:
            # this will happen when you have configuration files for devices
            # that are not in the database. You don't want the entire thing to
            # crash if that is the case.
            pass
    return devices + list(tmp_device_list)


class DatabaseJobSource(object):

    implements(IJobSource)

    def __init__(self, my_devices=None):
        self.logger = logging.getLogger(__name__ + '.DatabaseJobSource')
        if my_devices is None:
            self.my_devices = get_configured_devices
        else:
            self.my_devices = my_devices

    deferToThread = staticmethod(deferToThread)

    def deferForDB(self, func, *args, **kw):
        def wrapper(*args, **kw):
            # If there is no db connection yet on this thread, create a
            # connection and immediately commit, because rolling back the
            # first transaction on a connection loses the effect of
            # settings.TIME_ZONE when using postgres (see
            # https://code.djangoproject.com/ticket/17062).
            transaction.enter_transaction_management()
            transaction.managed()
            try:
                if connection.connection is None:
                    connection.cursor().close()
                    assert connection.connection is not None
                    transaction.commit()
                try:
                    return func(*args, **kw)
                except (DatabaseError, OperationalError, InterfaceError), error:
                    message = str(error)
                    if message == 'connection already closed' or \
                            message.startswith(
                            'terminating connection due to administrator command') or \
                            message.startswith(
                            'could not connect to server: Connection refused'):
                        self.logger.warning(
                            'Forcing reconnection on next db access attempt')
                        if connection.connection:
                            if not connection.connection.closed:
                                connection.connection.close()
                            connection.connection = None
                    raise
            finally:
                # In Django 1.2, the commit_manually() etc decorators only
                # commit or rollback the transaction if Django thinks there's
                # been a write to the database.  We don't want to leave
                # transactions dangling under any circumstances so we
                # unconditionally issue a rollback.  This might be a teensy
                # bit wastful, but it wastes a lot less time than figuring out
                # why your south migration appears to have got stuck...
                transaction.rollback()
                transaction.leave_transaction_management()
        return self.deferToThread(wrapper, *args, **kw)

    def _submit_health_check_jobs(self):
        """
        Checks which devices need a health check job and submits the needed
        health checks.
        """

        for device in Device.objects.all():
            if device.status != Device.IDLE:
                continue
            run_health_check = False
            if not device.device_type.health_check_job:
                run_health_check = False
            elif device.health_status == Device.HEALTH_UNKNOWN:
                run_health_check = True
            elif device.health_status == Device.HEALTH_LOOPING:
                run_health_check = True
            elif not device.last_health_report_job:
                run_health_check = True
            elif not device.last_health_report_job.end_time:
                run_health_check = True
            else:
                run_health_check = device.last_health_report_job.end_time < \
                    datetime.datetime.now() - datetime.timedelta(days=1)

            if run_health_check:
                device.initiate_health_check_job()

    def _get_job_queue(self):
        """
        Order of precedence:

        - health checks before everything else
        - all the rest of the jobs, sorted by priority, then submission time.

        Additionally, we also sort by target_group, so that if you have two
        multinode job groups with the same priority submitted at the same time,
        their sub jobs will be contiguous to each other in the list.  Lastly,
        we also sort by id to make sure we have a stable order and that jobs
        that came later into the system (as far as the DB is concerned) get
        later into the queue.
        """

        jobs = TestJob.objects.filter(status=TestJob.SUBMITTED)
        jobs = jobs.filter(actual_device=None)
        jobs = jobs.order_by('-health_check', '-priority', 'submit_time',
                             'vm_group', 'target_group', 'id')

        return jobs

    def _get_available_devices(self):
        """
        A list of idle devices, with private devices first.

        This order is used so that a job submitted by John Doe will prefer
        using John Doe's private devices over using public devices that could
        be available for other users who don't have their own.
        """
        devices = Device.objects.filter(status=Device.IDLE)
        devices = devices.order_by('is_public')

        return devices

    def _assign_jobs(self):
        jobs = list(self._get_job_queue())
        devices = list(self._get_available_devices())
        for job in jobs:
            device = find_device_for_job(job, devices)
            if device:
                job.actual_device = device
                job.submit_token = AuthToken.objects.create(user=job.submitter)
                device.current_job = job
                device.state_transition_to(Device.RESERVED, message="Reserved for job %s" % job.display_id)
                job.save()
                device.save()
                if device in devices:
                    devices.remove(device)

    def _kill_canceling(self, job):
        """
        Kills any remaining lava-dispatch processes via the pgid in the jobpid file

        :param job: the TestJob stuck in Canceling
        """
        pidrecord = os.path.join(job.output_dir, "jobpid")
        if os.path.exists(pidrecord):
            with open(pidrecord, 'r') as f:
                pgid = int(f.read())
                self.logger.info("Signalling SIGTERM to process group: %d" % pgid)
                try:
                    os.killpg(pgid, signal.SIGTERM)
                except OSError as e:
                    self.logger.info("Unable to kill process group %d: %s" % (pgid, e))
                    os.unlink(pidrecord)

    def getJobList_impl(self):
        """
        This method is called in a loop by the scheduler daemon service.
        It's goal is to return a list of jobs that are ready to be started.
        """
        self._handle_cancelling_jobs()

        if utils.is_master():
            self._submit_health_check_jobs()
            self._assign_jobs()

        my_devices = get_temporary_devices(self.my_devices())
        my_submitted_jobs = TestJob.objects.filter(
            status=TestJob.SUBMITTED,
            actual_device_id__in=my_devices,
        )

        my_ready_jobs = filter(lambda job: job.is_ready_to_start, my_submitted_jobs)

        transaction.commit()
        return my_ready_jobs

    def getJobList(self):
        return self.deferForDB(self.getJobList_impl)

    def _get_json_data(self, job):
        json_data = simplejson.loads(job.definition)
        if job.actual_device:
            json_data['target'] = job.actual_device.hostname
        elif job.requested_device:
            json_data['target'] = job.requested_device.hostname
        for action in json_data['actions']:
            if not action['command'].startswith('submit_results'):
                continue
            params = action['parameters']
            params['token'] = job.submit_token.secret
            parsed = urlparse.urlsplit(params['server'])
            netloc = job.submitter.username + '@' + parsed.hostname
            if parsed.port:
                netloc += ':' + str(parsed.port)
            parsed = list(parsed)
            parsed[1] = netloc
            params['server'] = urlparse.urlunsplit(parsed)
        json_data['health_check'] = job.health_check
        return json_data

    def getJobDetails_impl(self, job):
        return self._get_json_data(job)

    def getJobDetails(self, job):
        return self.deferForDB(self.getJobDetails_impl, job)

    def getOutputDirForJobOnBoard_impl(self, board_name):
        device = Device.objects.get(hostname=board_name)
        job = device.current_job
        return job.output_dir

    def getOutputDirForJobOnBoard(self, board_name):
        return self.deferForDB(self.getOutputDirForJobOnBoard_impl, board_name)

    def jobStarted_impl(self, job):
        job.status = TestJob.RUNNING

        # need to set the device RUNNING if device was RESERVED
        device = job.actual_device
        if device.status == Device.RESERVED:
            msg = "Started running job %s" % job.display_id
            device.state_transition_to(Device.RUNNING, message=msg, job=job)
        device.save()
        job.start_time = datetime.datetime.utcnow()
        shutil.rmtree(job.output_dir, ignore_errors=True)
        job.log_file.save('job-%s.log' % job.id, ContentFile(''), save=False)
        job.save()
        transaction.commit()

    def jobStarted(self, job):
        return self.deferForDB(self.jobStarted_impl, job)

    def jobCompleted_impl(self, board_name, exit_code, kill_reason):
        self.logger.debug('marking job as complete on %s', board_name)
        device = Device.objects.get(hostname=board_name)
        old_device_status = device.status
        new_device_status = None
        previous_state = device.previous_state()
        MAX_RETRIES = 3

        if old_device_status == Device.RUNNING:
            new_device_status = previous_state
        elif old_device_status == Device.OFFLINING:
            new_device_status = Device.OFFLINE
        elif old_device_status == Device.RESERVED:
            new_device_status = previous_state
        else:
            self.logger.error(
                "Unexpected device state in jobCompleted: %s" % device.status)
            new_device_status = Device.IDLE
        if new_device_status is None:
            new_device_status = Device.IDLE
        job = device.current_job

        # Temporary devices should be marked as RETIRED once the job is
        # complete or canceled.
        if job.is_vmgroup:
            try:
                if device.temporarydevice:
                    new_device_status = Device.RETIRED
            except TemporaryDevice.DoesNotExist:
                self.logger.debug("%s is not a tmp device" % device.hostname)

        device.device_version = _get_device_version(job.results_bundle)
        device.current_job = None
        if job.status == TestJob.RUNNING:
            if exit_code == 0:
                job.status = TestJob.COMPLETE
            else:
                job.status = TestJob.INCOMPLETE
        elif job.status == TestJob.CANCELING:
            job.status = TestJob.CANCELED
        else:
            self.logger.error(
                "Unexpected job state in jobCompleted: %s" % job.status)
            job.status = TestJob.COMPLETE

        msg = "Job %s completed" % job.display_id
        device.state_transition_to(new_device_status, message=msg, job=job)

        if job.health_check:
            device.last_health_report_job = job
            if device.health_status != Device.HEALTH_LOOPING:
                if job.status == TestJob.INCOMPLETE:
                    device.health_status = Device.HEALTH_FAIL
                    device.put_into_maintenance_mode(None, "Health Check Job Failed")
                elif job.status == TestJob.COMPLETE:
                    device.health_status = Device.HEALTH_PASS

        bundle_file = os.path.join(job.output_dir, 'result-bundle')
        if os.path.exists(bundle_file):
            with open(bundle_file) as f:
                results_link = f.read().strip()
            job._results_link = results_link
            sha1 = results_link.strip('/').split('/')[-1]
            try:
                bundle = Bundle.objects.get(content_sha1=sha1)
            except Bundle.DoesNotExist:
                pass
            else:
                job._results_bundle = bundle

        job.end_time = datetime.datetime.utcnow()
        token = job.submit_token
        job.submit_token = None
        device.save()
        job.save()
        # notification needs to have the correct status in the database
        for retry in range(MAX_RETRIES):
            try:
                transaction.commit()
                self.logger.debug('%s job completed and status saved' % job.id)
                break
            except TransactionRollbackError as err:
                self.logger.warn('Retrying %s job completion ... %s' % (job.id, err))
                continue
        if utils.is_master():
            try:
                job.send_summary_mails()
            except:
                # Better to catch all exceptions here and log it than have this
                # method fail.
                self.logger.exception(
                    'sending job summary mails for job %r failed', job.pk)
        else:
            worker = WorkerData()
            worker.notify_on_incomplete(job.id)
        # need the token for the XMLRPC
        token.delete()

    def jobCompleted(self, board_name, exit_code, kill_reason):
        return self.deferForDB(self.jobCompleted_impl, board_name, exit_code, kill_reason)

    def jobCheckForCancellation_impl(self, board_name):
        device = Device.objects.get(hostname=board_name)
        job = device.current_job
        return job.status != TestJob.RUNNING

    def jobCheckForCancellation(self, board_name):
        return self.deferForDB(self.jobCheckForCancellation_impl, board_name)

    def _handle_cancelling_jobs(self):
        cancel_list = TestJob.objects.all().filter(status=TestJob.CANCELING)
        # Pick up TestJob objects in Canceling and ensure that the cancel completes.
        # call _kill_canceling to terminate any lava-dispatch calls
        # Explicitly set a DeviceStatusTransition as jobs which are stuck in Canceling
        #  may already have lost connection to the SchedulerMonitor via twisted.
        # Call TestJob.cancel to reset the TestJob status
        if len(cancel_list) > 0:
            self.logger.debug("Number of jobs in cancelling status %d" % len(cancel_list))
            for job in cancel_list:
                if job.actual_device and job.actual_device.hostname in self.my_devices():
                    self.logger.debug("Looking for pid of dispatch job %s in %s" % (job.id, job.output_dir))
                    self._kill_canceling(job)
                    device = Device.objects.get(hostname=job.actual_device.hostname)
                    if device.status == Device.RUNNING:
                        previous_state = device.previous_state()
                        if previous_state is None:
                            previous_state = Device.IDLE
                        if job.is_vmgroup:
                            try:
                                if device.temporarydevice:
                                    previous_state = Device.RETIRED
                            except TemporaryDevice.DoesNotExist:
                                self.logger.debug("%s is not a tmp device" % device.hostname)
                        self.logger.debug("Transitioning %s to %s" % (device.hostname, previous_state))
                        device.current_job = None
                        msg = "Job %s cancelled" % job.display_id
                        device.state_transition_to(previous_state, message=msg,
                                                   job=job)
                    self.logger.debug('Marking job %s as cancelled on %s' % (job.id, job.actual_device))
                    job.cancel()
                    transaction.commit()


def _get_device_version(bundle):
    if bundle is None:
        return None
    try:
        lava_test_run = bundle.test_runs.filter(test__test_id='lava')[0]
        version_attribute = lava_test_run.attributes.filter(name='target.device_version')[0]
        return version_attribute.value
    except IndexError:
        return 'unknown'
