import datetime
import logging
import os
import shutil
import urlparse
import signal
from dashboard_app.models import Bundle

import django
from django.core.files.base import ContentFile
from django.db import connection
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.utils import DatabaseError
from django.utils import timezone

from linaro_django_xmlrpc.models import AuthToken
from psycopg2.extensions import TransactionRollbackError
import simplejson

from twisted.internet.threads import deferToThread  # pylint: disable=unused-import

from zope.interface import implements

import lava_dispatcher.config as dispatcher_config

from lava_scheduler_app.models import (
    Device,
    TestJob,
    TemporaryDevice,
    JSONDataError,
)
from lava_scheduler_app import utils
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


def find_device_for_job(job, device_list):
    """
    If the device has the same tags as the job or all the tags required
    for the job and some others which the job does not explicitly specify,
    check if this device be assigned to this job for this user.
    Works for pipeline jobs and old-style jobs but refuses to select a
    non-pipeline device for a pipeline job. Pipeline devices are explicitly
    allowed to run non-pipeline jobs.

    Note: with a large queue and a lot of devices, this function can be a
    significant delay.
    """
    if job.dynamic_connection:
        # secondary connection, the "host" has a real device
        return None
    logger = logging.getLogger(__name__ + '.DatabaseJobSource')
    for device in device_list:
        if device.current_job:
            if device.device_type != job.requested_device_type:
                continue
            if job.requested_device and device == job.requested_device:
                # forced health checks complicate this condition as it would otherwise
                # be an error to find the device here when it should not be IDLE.
                continue
            # warn the admin that this needs human intervention
            bad_job = TestJob.objects.get(id=device.current_job.id)
            logger.warning("Refusing to reserve %s for %s - current job is %s" % (
                device, job, bad_job
            ))
            device_list.remove(device)
        if device.is_exclusive and not job.is_pipeline:
            device_list.remove(device)
    if not device_list:
        return None
    # forced health check support
    if job.health_check is True:
        if job.requested_device.status == Device.OFFLINE:
            return job.requested_device
    for device in device_list:
        if job.is_vmgroup:
            # special handling, tied directly to the TestJob within the vmgroup
            # mask to a Temporary Device to be able to see vm_group of the device
            tmp_dev = TemporaryDevice.objects.filter(hostname=device.hostname)
            if tmp_dev and job.vm_group != tmp_dev[0].vm_group:
                continue
        if job.is_pipeline and not device.is_pipeline:
            continue
        if device == job.requested_device:
            if device.can_submit(job.submitter) and\
                    set(job.tags.all()) & set(device.tags.all()) == set(job.tags.all()):
                return device
        if device.device_type == job.requested_device_type:
            if device.can_submit(job.submitter) and\
                    set(job.tags.all()) & set(device.tags.all()) == set(job.tags.all()):
                return device
    return None


def get_configured_devices():
    return dispatcher_config.list_devices()


def get_temporary_devices(devices):
    """
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
                # might be a teensy bit wastful, but it wastes a lot less time
                # than figuring out why your south migration appears to have
                # got stuck...
                transaction.rollback()
                transaction.set_autocommit(True)
        return self.deferToThread(wrapper, *args, **kw)

    def _commit_transaction(self, src=None):
        for retry in range(MAX_RETRIES):
            try:
                transaction.commit()
                self.logger.debug('%s transaction committed', src)
                break
            except TransactionRollbackError as err:
                self.logger.warn('retrying transaction %s', err)
                continue

    def _submit_health_check_jobs(self):
        """
        Checks which devices need a health check job and submits the needed
        health checks.
        Looping is only active once a device is offline.
        """

        for device in Device.objects.filter(
                Q(status=Device.IDLE) | Q(status=Device.OFFLINE, health_status=Device.HEALTH_LOOPING)):
            # FIXME: We do not support health check job for pipeline devices
            #        yet, hence remove exclusive pipeline devices.
            if device.is_exclusive:
                continue
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
                    timezone.now() - datetime.timedelta(days=1)

            if run_health_check:
                self.logger.debug('submit health check for %s',
                                  device.hostname)
                try:
                    device.initiate_health_check_job()
                except JSONDataError:
                    # already logged, don't allow the daemon to fail.
                    pass

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

        Pipeline jobs are allowed to be assigned but the actual running of
        a job on a reserved pipeline device is down to the dispatcher-master.
        """

        jobs = TestJob.objects.filter(status=TestJob.SUBMITTED)
        jobs = jobs.filter(actual_device=None)
        jobs = jobs.order_by('-health_check', '-priority', 'submit_time',
                             'vm_group', 'target_group', 'id')

        if len(jobs):
            self.logger.info("Job queue length: %d", len(jobs))
        return jobs

    def _get_available_devices(self):
        """
        A list of idle devices, with private devices first.

        This order is used so that a job submitted by John Doe will prefer
        using John Doe's private devices over using public devices that could
        be available for other users who don't have their own.

        Forced health checks ignore this constraint.
        """
        devices = Device.objects.filter(status=Device.IDLE).order_by('is_public')
        return devices

    def _validate_non_idle_devices(self, reserved_devices, idle_devices):
        """
        only check those devices which we *know* should have been changed
        and check that the changes are correct.
        """
        errors = []
        for device_name in reserved_devices:
            device = Device.objects.get(hostname=device_name)  # force re-load
            if device.status not in [Device.RESERVED, Device.RUNNING]:
                self.logger.warning("Failed to properly reserve %s", device)
                errors.append('r')
            if device in idle_devices:
                self.logger.warning("%s is still listed as available!", device)
                errors.append('a')
            if not device.current_job:
                self.logger.warning("Invalid reservation, %s has no current job.", device)
                return False
            if not device.current_job.actual_device:
                self.logger.warning("Invalid reservation, %s has no actual device.", device.current_job)
                return False
            if device.hostname != device.current_job.actual_device.hostname:
                self.logger.warning(
                    "%s is not the same device as %s", device, device.current_job.actual_device)
                errors.append('j')
        return errors == []

    def _validate_queue(self):
        """
        Invalid reservation states can leave zombies which are SUBMITTED with an actual device.
        These jobs get ignored by the get_job_queue function and therfore by assign_jobs *unless*
        another job happens to reference that specific device.
        """
        jobs = TestJob.objects.filter(status=TestJob.SUBMITTED)
        jobs = jobs.filter(actual_device__isnull=False)
        for job in jobs:
            if not job.actual_device.current_job:
                device = Device.objects.get(hostname=job.actual_device.hostname)
                if device.status != Device.IDLE:
                    continue
                self.logger.warning(
                    "Fixing up a broken device reservation for queued %s on %s", job, device.hostname)
                device.status = Device.RESERVED
                device.current_job = job
                device.save(update_fields=['status', 'current_job'])

    def _validate_idle_device(self, job, device):
        """
        The problem here is that instances with a lot of devices would spend a lot of time
        refetching all of the device details every scheduler tick when it is only under
        particular circumstances that an error is made. The safe option is always to refuse
        to use a device which has changed status.
        get() evaluates immediately.
        :param job: job to have a device assigned
        :param device: device to refresh and check
        :return: True if device can be reserved
        """
        # FIXME: do this properly in the dispatcher master.
        # FIXME: fold the find_device current_job check into this routine for clarity
        # FIXME: isolate forced health check requirements
        if django.VERSION >= (1, 8):
            # https://docs.djangoproject.com/en/dev/ref/models/instances/#refreshing-objects-from-database
            device.refresh_from_db()
        else:
            device = Device.objects.get(hostname=device.hostname)
        # to be valid for reservation, no queued TestJob can reference this device
        jobs = TestJob.objects.filter(
            status__in=[TestJob.RUNNING, TestJob.SUBMITTED, TestJob.CANCELING],
            actual_device=device)
        if jobs:
            self.logger.warning(
                "%s (which has current_job %s) is already referenced by %d jobs %s",
                device.hostname, device.current_job, len(jobs), [job.id for job in jobs])
            if len(jobs) == 1:
                self.logger.warning(
                    "Fixing up a broken device reservation for %s on %s",
                    jobs[0], device.hostname)
                device.status = Device.RESERVED
                device.current_job = jobs[0]
                device.save(update_fields=['status', 'current_job'])
                return False
        # forced health check support
        if job.health_check:
            # only assign once the device is offline.
            if device.status not in [Device.OFFLINE, Device.IDLE]:
                self.logger.warning("Refusing to reserve %s for health check, not IDLE or OFFLINE", device)
                return False
        elif device.status is not Device.IDLE:
            self.logger.warning("Refusing to reserve %s which is not IDLE", device)
            return False
        if device.current_job:
            self.logger.warning("Device %s already has a current job", device)
            return False
        return True

    def _assign_jobs(self):
        """
        Check all jobs against all available devices and assign only if all conditions are met
        This routine needs to remain fast, so has to manage local cache variables of device status but
        still cope with a job queue over 1,000 and a device matrix of over 100. The main load is in
        find_device_for_job as *all* jobs in the queue must be checked at each tick. (A job far back in
        the queue may be the only job which exactly matches the most recent devices to become available.)

        When viewing the logs of these operations, the device will be Idle when Assigning to a Submitted
        job. That job may be for a device_type or a specific device (typically health checks use a specific
        device). The device will be Reserved when Assigned to a Submitted job on that device - the type will
        not be mentioned. The total number of assigned jobs and devices will be output at the end of each tick.
        Finally, the reserved device is removed from the local cache of available devices.

        Warnings are emitted if the device states are not as expected, before or after assignment.
        """
        # FIXME: this function needs to be moved to dispatcher-master when lava_scheduler_daemon is disabled.
        # FIXME: in dispatcher-master, implement as in share/zmq/assign.[dia|png]
        # FIXME: Make the forced health check constraint explicit
        # evaluate the testjob query set using list()
        self._validate_queue()
        jobs = list(self._get_job_queue())
        if not jobs:
            return
        assigned_jobs = []
        reserved_devices = []
        # this takes a significant amount of time when under load, only do it once per tick
        devices = list(self._get_available_devices())
        # a forced health check can be assigned even if the device is not in the list of idle devices.
        for job in jobs:
            device = find_device_for_job(job, devices)
            if device:
                if not self._validate_idle_device(job, device):
                    self.logger.debug("Removing %s from the list of available devices",
                                      str(device.hostname))
                    devices.remove(device)
                    continue
                self.logger.info("Assigning %s for %s", device, job)
                # avoid catching exceptions inside atomic (exceptions are slow too)
                # https://docs.djangoproject.com/en/1.7/topics/db/transactions/#controlling-transactions-explicitly
                if AuthToken.objects.filter(user=job.submitter).count():
                    job.submit_token = AuthToken.objects.filter(user=job.submitter).first()
                else:
                    job.submit_token = AuthToken.objects.create(user=job.submitter)
                try:
                    # Make this sequence atomic
                    with transaction.atomic():
                        job.actual_device = device
                        job.save()
                        device.current_job = job
                        # implicit device save in state_transition_to()
                        device.state_transition_to(
                            Device.RESERVED, message="Reserved for job %s" % job.display_id, job=job)
                except IntegrityError:
                    # Retry in the next call to _assign_jobs
                    self.logger.warning(
                        "Transaction failed for job %s, device %s", job.display_id, device.hostname)
                assigned_jobs.append(job.id)
                reserved_devices.append(device.hostname)
                self.logger.info("Assigned %s to %s", device, job)
                if device in devices:
                    self.logger.debug("Removing %s from the list of available devices",
                                      str(device.hostname))
                    devices.remove(device)
        # re-evaluate the devices query set using list() now that the job loop is complete
        devices = list(self._get_available_devices())
        postprocess = self._validate_non_idle_devices(reserved_devices, devices)
        if postprocess and reserved_devices:
            self.logger.debug("All queued jobs checked, %d devices reserved and validated", len(reserved_devices))

        # worker heartbeat must not occur within this loop
        self.logger.info("Assigned %d jobs on %s devices", len(assigned_jobs), len(reserved_devices))

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

        if utils.is_master():
            # FIXME: move into dispatcher-master
            self._submit_health_check_jobs()
            self._assign_jobs()

        # from here on, ignore pipeline jobs.
        my_devices = get_temporary_devices(self.my_devices())
        my_submitted_jobs = TestJob.objects.filter(
            status=TestJob.SUBMITTED,
            actual_device_id__in=my_devices,
            is_pipeline=False
        )

        my_ready_jobs = filter(lambda job: job.is_ready_to_start, my_submitted_jobs)

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
        job.log_file.save('job-%s.log' % job.id, ContentFile(''), save=False)
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
    if bundle is None:
        return None
    try:
        lava_test_run = bundle.test_runs.filter(test__test_id='lava')[0]
        version_attribute = lava_test_run.attributes.filter(name='target.device_version')[0]
        return version_attribute.value
    except IndexError:
        return 'unknown'
