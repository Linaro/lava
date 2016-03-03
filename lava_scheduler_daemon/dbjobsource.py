import logging
import os
import shutil
import urlparse
import signal
from dashboard_app.models import Bundle

from django.db import connection
from django.db import transaction
from django.db.utils import DatabaseError
from django.utils import timezone

from psycopg2.extensions import TransactionRollbackError
import simplejson

from twisted.internet.threads import deferToThread  # pylint: disable=unused-import

from zope.interface import implements

import lava_dispatcher.config as dispatcher_config

from lava_scheduler_app.models import (
    Device,
    TestJob,
    TemporaryDevice,
)
from lava_scheduler_app import utils
from lava_scheduler_app.dbutils import (
    submit_health_check_jobs,
    assign_jobs,
)
from lava_scheduler_daemon.worker import WorkerData
from lava_scheduler_daemon.jobsource import IJobSource


MAX_RETRIES = 3


try:
    from psycopg2 import InterfaceError, OperationalError
except ImportError:
    class InterfaceError(Exception):
        pass

    class OperationalError(Exception):
        pass


def get_configured_devices():
    """ Deprecated """
    return dispatcher_config.list_devices()


def get_temporary_devices(devices):
    """ Deprecated
    :param devices: list of device HOSTNAMES
    :return: list of HOSTNAMES with hostnames of temporary devices appended
    """
    tmp_device_list = set()
    logger = logging.getLogger(__name__ + '.DatabaseJobSource')
    if type(devices) is not list:
        logger.warning("Programming error: %s needs to be a list", devices)
        return None
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
            # can also happen if a programming error results in sending
            # a list of devices, not a list of hostnames.
            if type(dev) not in [unicode, str]:
                logger.warning("Programming error: %s needs to be a list of hostnames")
                return None
            pass
    return devices + list(tmp_device_list)


class DatabaseJobSource(object):
    """ Deprecated """

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
            transaction.set_autocommit(False)
            try:
                if connection.connection is None:
                    connection.cursor().close()
                    assert connection.connection is not None
                try:
                    return func(*args, **kw)
                except (DatabaseError, OperationalError, InterfaceError), error:
                    message = str(error)
                    if message == 'connection already closed' or message.startswith(
                            'terminating connection due to administrator command') or message.startswith(
                                'could not connect to server: Connection refused'):
                        self.logger.warning(
                            'Forcing reconnection on next db access attempt')
                        if connection.connection:
                            if not connection.connection.closed:
                                connection.connection.close()
                            connection.connection = None
                    raise
            finally:
                # We don't want to leave transactions dangling under any
                # circumstances so we unconditionally issue a rollback.  This
                # might be a teensy bit wasteful, but it wastes a lot less time
                # than figuring out why your database migration appears to have
                # got stuck...
                transaction.rollback()
                transaction.set_autocommit(True)
        return self.deferToThread(wrapper, *args, **kw)

    def _commit_transaction(self, src=None):
        if connection.in_atomic_block:
            return
        for retry in range(MAX_RETRIES):
            try:
                transaction.commit()
                self.logger.debug('%s transaction committed', src)
                break
            except TransactionRollbackError as err:
                self.logger.warn('retrying transaction %s', err)
                continue

    def _kill_canceling(self, job):
        """
        Kills any remaining lava-dispatch processes via the pgid in the jobpid file

        :param job: the TestJob stuck in Canceling
        """
        pidrecord = os.path.join(job.output_dir, "jobpid")
        if os.path.exists(pidrecord):
            with open(pidrecord, 'r') as f:
                pgid = int(f.read())
                self.logger.info("Signalling SIGTERM to process group: %d", pgid)
                try:
                    os.killpg(pgid, signal.SIGTERM)
                except OSError as e:
                    self.logger.info("Unable to kill process group %d: %s", pgid, e)
                    os.unlink(pidrecord)

    def getJobList_impl(self):
        """
        This method is called in a loop by the scheduler daemon service.
        It's goal is to return a list of jobs that are ready to be started.
        Note: handles both old and pipeline jobs but only so far as putting
        devices into a Reserved state. Running pipeline jobs from Reserved
        is the sole concern of the dispatcher-master.
        """
        self._handle_cancelling_jobs()

        # FIXME: to move into the dispatcher-master
        if utils.is_master():
            submit_health_check_jobs()
            assign_jobs()

        # from here on, ignore pipeline jobs.
        my_devices = get_temporary_devices(self.my_devices())
        my_submitted_jobs = TestJob.objects.filter(
            status=TestJob.SUBMITTED,
            actual_device_id__in=my_devices,
            is_pipeline=False
        )

        my_ready_jobs = filter(lambda job: job.is_ready_to_start, my_submitted_jobs)

        if not connection.in_atomic_block:
            self._commit_transaction(src='getJobList_impl')
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
        if job:
            return job.output_dir
        return None

    def getOutputDirForJobOnBoard(self, board_name):
        return self.deferForDB(self.getOutputDirForJobOnBoard_impl, board_name)

    def jobStarted_impl(self, job):
        job.status = TestJob.RUNNING

        # need to set the device RUNNING if device was RESERVED
        device = job.actual_device
        if device.status == Device.RESERVED:
            msg = "Started running job %s" % job.display_id
            device.state_transition_to(Device.RUNNING, message=msg, job=job)
            self._commit_transaction(src='%s state' % device.hostname)
            self.logger.info('%s started running job %s', device.hostname,
                             job.id)
        device.save()
        job.start_time = timezone.now()
        if job.output_dir:
            shutil.rmtree(job.output_dir, ignore_errors=True)
        job.save()
        self._commit_transaction(src='jobStarted_impl')

    def jobStarted(self, job):
        return self.deferForDB(self.jobStarted_impl, job)

    def jobCompleted_impl(self, job_id, board_name, exit_code, kill_reason):
        if not job_id:
            self.logger.debug('job completion called without a job id on %s',
                              board_name)
            return
        else:
            job = TestJob.objects.get(id=job_id)

        self.logger.debug('marking job as complete on %s', board_name)
        device = Device.objects.get(hostname=board_name)
        old_device_status = device.status
        self.logger.debug('old device status %s, job state %s' % (
            Device.STATUS_CHOICES[old_device_status][1],
            TestJob.STATUS_CHOICES[job.status][1]))

        if old_device_status == Device.RUNNING:
            new_device_status = Device.IDLE
        elif old_device_status == Device.OFFLINING:
            new_device_status = Device.OFFLINE
        elif old_device_status == Device.RESERVED:
            new_device_status = Device.IDLE
        else:
            self.logger.error(
                "Unexpected device state in jobCompleted: %s", device.status)
            new_device_status = Device.IDLE
        if new_device_status is None:
            self.logger.debug("unhandled old device state")
            new_device_status = Device.IDLE

        self.logger.debug('new device status %s, job state %s' % (
            Device.STATUS_CHOICES[new_device_status][1],
            TestJob.STATUS_CHOICES[job.status][1]))

        # Temporary devices should be marked as RETIRED once the job is
        # complete or canceled.
        if job.is_vmgroup:
            try:
                if device.temporarydevice:
                    new_device_status = Device.RETIRED
                    device.current_job = None
            except TemporaryDevice.DoesNotExist:
                self.logger.debug("%s is not a tmp device", device.hostname)

        if job.status == TestJob.RUNNING:
            if exit_code == 0:
                job.status = TestJob.COMPLETE
            else:
                job.status = TestJob.INCOMPLETE
        elif job.status == TestJob.CANCELING:
            job.status = TestJob.CANCELED
        else:
            self.logger.error("Unexpected job state in jobCompleted: %s, probably we are trying job completion for a different job", job.status)
            return

        self.logger.debug('changed job status to %s' % (
            TestJob.STATUS_CHOICES[job.status][1]))

        if job.health_check:
            device.last_health_report_job = job
            self.logger.debug("old device health status %s" % Device.HEALTH_CHOICES[device.health_status][1])
            if device.health_status != Device.HEALTH_LOOPING:
                if job.status == TestJob.INCOMPLETE:
                    device.health_status = Device.HEALTH_FAIL
                    self.logger.debug("taking %s offline, failed health check job %s" % (
                        device.hostname, job_id))
                    device.put_into_maintenance_mode(None, "Health Check Job Failed")
                    # update the local variable to track the effect of the external function call
                    new_device_status = device.status
                    if new_device_status == Device.OFFLINING:
                        new_device_status = Device.OFFLINE  # offlining job is complete.
                elif job.status == TestJob.COMPLETE:
                    device.health_status = Device.HEALTH_PASS
                    if old_device_status == Device.RUNNING:
                        new_device_status = Device.IDLE
                device.save()
            self.logger.debug("new device health status %s" % Device.HEALTH_CHOICES[device.health_status][1])

        if job.output_dir and job.output_dir != '':
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
                    device.device_version = _get_device_version(job.results_bundle)
        else:
            self.logger.warning("[%d] lacked a usable output_dir", job.id)

        self.logger.debug('new device status %s, job state %s' % (
            Device.STATUS_CHOICES[new_device_status][1],
            TestJob.STATUS_CHOICES[job.status][1]))

        job.end_time = timezone.now()

        job.submit_token = None

        device.current_job = None

        msg = "Job %s completed" % job.display_id
        device.state_transition_to(new_device_status, message=msg, job=job)
        self._commit_transaction(src='%s state' % device.hostname)

        device.save()
        job.save()
        self._commit_transaction(src='jobCompleted_impl')
        self.logger.info('job %s completed on %s', job.id, device.hostname)

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

    def jobCompleted(self, job_id, board_name, exit_code, kill_reason):
        return self.deferForDB(self.jobCompleted_impl, job_id, board_name,
                               exit_code, kill_reason)

    def jobCheckForCancellation_impl(self, board_name):
        device = Device.objects.get(hostname=board_name)
        job = device.current_job
        return job.status != TestJob.RUNNING

    def jobCheckForCancellation(self, board_name):
        return self.deferForDB(self.jobCheckForCancellation_impl, board_name)

    def _handle_cancelling_jobs(self):
        cancel_list = TestJob.objects.filter(status=TestJob.CANCELING, is_pipeline=False)
        # Pick up TestJob objects in Canceling and ensure that the cancel completes.
        # call _kill_canceling to terminate any lava-dispatch calls
        # Explicitly set a DeviceStatusTransition as jobs which are stuck in Canceling
        #  may already have lost connection to the SchedulerMonitor via twisted.
        # Call TestJob.cancel to reset the TestJob status
        if len(cancel_list) > 0:
            self.logger.debug("Number of jobs in cancelling status %d", len(cancel_list))
            for job in cancel_list:
                device_list = get_temporary_devices(self.my_devices())
                if job.actual_device and job.actual_device.hostname in device_list:
                    self.logger.debug("Looking for pid of dispatch job %s in %s", job.id, job.output_dir)
                    self._kill_canceling(job)
                    device = Device.objects.get(hostname=job.actual_device.hostname)
                    transition_device = False
                    if device.status == Device.OFFLINING:
                        new_state = Device.OFFLINE
                        transition_device = True
                    if device.status in [Device.RESERVED, Device.RUNNING]:
                        new_state = Device.IDLE
                        transition_device = True
                    if job.is_vmgroup:
                        try:
                            # any canceled temporary device always goes to RETIRED
                            # irrespective of previous state or code above
                            if device.temporarydevice:
                                new_state = Device.RETIRED
                                transition_device = True
                        except TemporaryDevice.DoesNotExist:
                            self.logger.debug("%s is not a tmp device", device.hostname)
                    if transition_device:
                        device.current_job = None  # creating the transition calls save()
                        self.logger.debug("Transitioning %s to %s", device.hostname, new_state)
                        msg = "Job %s cancelled" % job.display_id
                        device.state_transition_to(new_state, message=msg, job=job)
                        self._commit_transaction(src='%s state' % device.hostname)
                        self.logger.info('job %s cancelled on %s', job.id, job.actual_device)
                    job.cancel()
                    self._commit_transaction(src='_handle_cancelling_jobs')


def _get_device_version(bundle):
    """ Deprecated """
    if bundle is None:
        return None
    try:
        lava_test_run = bundle.test_runs.filter(test__test_id='lava')[0]
        version_attribute = lava_test_run.attributes.filter(name='target.device_version')[0]
        return version_attribute.value
    except IndexError:
        return 'unknown'
