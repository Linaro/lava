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

import simplejson

from twisted.internet.threads import deferToThread

from zope.interface import implements

import lava_dispatcher.config as dispatcher_config

from lava_scheduler_app.models import (
    Device,
    DeviceStateTransition,
    JSONDataError,
    TestJob)
from lava_scheduler_app import utils
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


class DatabaseJobSource(object):

    implements(IJobSource)

    def __init__(self):
        self.logger = logging.getLogger(__name__ + '.DatabaseJobSource')

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

    def _get_health_check_jobs(self):
        """Gets the list of devices and checks which are the devices that
        require health check.

        Returns JOB_LIST which is a list of health check jobs. If no health
        check jobs are available returns an empty list.
        """
        job_list = []

        for device in Device.objects.all():
            if device.status != Device.IDLE:
                continue
            if not device.device_type.health_check_job:
                run_health_check = False
            elif device.health_status == Device.HEALTH_UNKNOWN:
                run_health_check = True
            elif device.health_status == Device.HEALTH_LOOPING:
                run_health_check = True
            elif not device.last_health_report_job:
                run_health_check = True
            else:
                run_health_check = device.last_health_report_job.end_time < \
                    datetime.datetime.now() - datetime.timedelta(days=1)
            if run_health_check:
                job_list.append(self._getHealthCheckJobForBoard(device))
        return job_list

    def _fix_device(self, device, job):
        """Associate an available/idle DEVICE to the given JOB.

        If the MultiNode job is waiting as Submitted, the device
        could be running a different job.
        Returns the job with actual_device set to DEVICE.

        If we are unable to grab the DEVICE then we return None.
        """
        if device.status == Device.RUNNING:
            return None
        DeviceStateTransition.objects.create(
            created_by=None, device=device, old_state=device.status,
            new_state=Device.RESERVED, message=None, job=job).save()
        device.status = Device.RESERVED
        device.current_job = job
        try:
            # The unique constraint on current_job may cause this to
            # fail in the case of concurrent requests for different
            # boards grabbing the same job.  If there are concurrent
            # requests for the *same* board they may both return the
            # same job -- this is an application level bug though.
            device.save()
        except IntegrityError:
            self.logger.info(
                "job %s has been assigned to another board -- rolling back",
                job.id)
            transaction.rollback()
            return None
        else:
            job.actual_device = device
            job.log_file.save(
                'job-%s.log' % job.id, ContentFile(''), save=False)
            job.submit_token = AuthToken.objects.create(user=job.submitter)
            job.definition = simplejson.dumps(self._get_json_data(job),
                                              sort_keys=True,
                                              indent=4 * ' ')
            job.save()
            transaction.commit()
        return job

    def _delay_multinode_scheduling(self, job_list):
        """Remove scheduling multinode jobs until all the jobs in the
        target_group are assigned devices.
        """
        final_job_list = copy.deepcopy(job_list)
        for job in job_list:
            if job.is_multinode:
                multinode_jobs = TestJob.objects.all().filter(
                    target_group=job.target_group)

                jobs_with_device = 0
                for multinode_job in multinode_jobs:
                    if multinode_job.actual_device:
                        jobs_with_device += 1

                if len(multinode_jobs) != jobs_with_device:
                    for m_job in multinode_jobs:
                        if m_job in final_job_list:
                            final_job_list.remove(m_job)

        return final_job_list

    def _process_multinode_jobs(self, job):
        job_list = []
        if job.is_multinode:
            multinode_jobs = TestJob.objects.all().filter(
                target_group=job.target_group)

            for m_job in multinode_jobs:
                devices = Device.objects.all().filter(
                    device_type=m_job.requested_device_type,
                    status=Device.IDLE)
                if len(devices) > 0:
                    f_job = self._fix_device(devices[0], m_job)
                    if f_job:
                        job_list.append(f_job)

        return job_list

    def _assign_jobs(self, jobs):
        job_list = self._get_health_check_jobs()
        devices = None

        for job in jobs:
            if job.is_multinode and not job.actual_device:
                job_list = job_list + self._process_multinode_jobs(job)
            else:
                if job.actual_device:
                    job_list.append(job)
                elif job.requested_device:
                    self.logger.debug("Checking Requested Device")
                    devices = Device.objects.all().filter(
                        hostname=job.requested_device.hostname,
                        status=Device.IDLE)
                elif job.requested_device_type:
                    self.logger.debug("Checking Requested Device Type")
                    devices = Device.objects.all().filter(
                        device_type=job.requested_device_type,
                        status=Device.IDLE)
                else:
                    continue
                if devices:
                    for d in devices:
                        if job:
                            job = self._fix_device(d, job)
                        if job:
                            job_list.append(job)

        return job_list

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

    def _device_heartbeat(self):
        """LAST_HEARTBEAT and WORKER_HOSTNAME fields gets updated for each
        configured device.
        """
        devices = Device.objects.all()
        configured_boards = [
            x.hostname for x in dispatcher_config.get_devices()]
        for device in devices:
            if device.hostname in configured_boards:
                device.worker_hostname = socket.getfqdn()
                device.last_heartbeat = datetime.datetime.utcnow()
                device.save()
                transaction.commit()
                self.logger.debug("Heartbeat updated for %s ..." %
                                  device.hostname)

            # Update device status based on heartbeat timestamp
            device.too_long_since_last_heartbeat()
            transaction.commit()

    def getJobList_impl(self):
        # FIXME the heartbeat is BROKEN so let's disable it for now.
        # self._device_heartbeat()

        job_list = TestJob.objects.all().filter(
            status=TestJob.SUBMITTED).order_by('-health_check', '-priority',
                                               'submit_time')

        cancel_list = TestJob.objects.all().filter(status=TestJob.CANCELING)
        # Pick up TestJob objects in Canceling and ensure that the cancel completes.
        # call _kill_canceling to terminate any lava-dispatch calls
        # Explicitly set a DeviceStatusTransition as jobs which are stuck in Canceling
        #  may already have lost connection to the SchedulerMonitor via twisted.
        # Call TestJob.cancel to reset the TestJob status
        if len(cancel_list) > 0:
            self.logger.debug("Number of jobs in cancelling status %d" % len(cancel_list))
            for job in cancel_list:
                if job.actual_device:
                    self.logger.debug("Looking for pid of dispatch job %s in %s" % (job.id, job.output_dir))
                    self._kill_canceling(job)
                    device = Device.objects.get(hostname=job.actual_device.hostname)
                    if device.status == Device.RUNNING:
                        self.logger.debug("Transitioning %s to Idle" % device.hostname)
                        device.current_job = None
                        old_status = device.status
                        device.status = Device.IDLE
                        device.save()
                        msg = "Cancelled job: %s from list" % job.id
                        DeviceStateTransition.objects.create(
                            created_by=None, device=device, old_state=old_status,
                            new_state=device.status, message=msg, job=job).save()
                    self.logger.debug('Marking job %s as cancelled on %s' % (job.id, job.actual_device))
                    job.cancel()
                    transaction.commit()

        if utils.is_master():
            self.logger.debug("Boards assigned to jobs ...")
            job_list = self._assign_jobs(job_list)

        self.logger.debug("Job list returned ...")
        return self._delay_multinode_scheduling([job for job in job_list])

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

    def _getHealthCheckJobForBoard(self, device):
        job_json = device.device_type.health_check_job
        if not job_json:
            # This should never happen, it's a logic error.
            self.logger.error(
                "no job_json in getHealthCheckJobForBoard for %r", device)
            device.put_into_maintenance_mode(
                None, "no job_json in getHealthCheckJobForBoard")
            return None
        else:
            user = User.objects.get(username='lava-health')
            job_data = simplejson.loads(job_json)
            job_data['target'] = device.hostname
            job_json = simplejson.dumps(job_data)
            try:
                return TestJob.from_json_and_user(job_json, user, True)
            except (JSONDataError, ValueError) as e:
                self.logger.exception(
                    "TestJob.from_json_and_user failed in _getHealthCheckJobForBoard")
                device.put_into_maintenance_mode(
                    None, "TestJob.from_json_and_user failed for health job: %s" % e)
                return None

    def _getJobFromQueue(self, device):
        jobs_for_device = TestJob.objects.all().filter(
            Q(requested_device=device)
            | Q(requested_device_type=device.device_type),
            status=TestJob.SUBMITTED)
        jobs_for_device = jobs_for_device.extra(
            select={
                'is_targeted': 'requested_device_id is not NULL',
            },
            where=[
                # In human language, this is saying "where the number of
                # tags that are on the job but not on the device is 0"
                '''(select count(*) from lava_scheduler_app_testjob_tags
                     where testjob_id = lava_scheduler_app_testjob.id
                       and tag_id not in (select tag_id
                                            from lava_scheduler_app_device_tags
                                           where device_id = '%s')) = 0'''
                % device.hostname,
            ],
            order_by=['-is_targeted', '-priority', 'submit_time'])
        jobs = jobs_for_device[:1]
        if jobs:
            return jobs[0]
        else:
            return None

    def getJobDetails_impl(self, job):
        job.status = TestJob.RUNNING
        # need to set the device RUNNING if device was RESERVED
        if job.actual_device.status == Device.RESERVED:
            DeviceStateTransition.objects.create(
                created_by=None, device=job.actual_device, old_state=job.actual_device.status,
                new_state=Device.RUNNING, message=None, job=job).save()
            job.actual_device.status = Device.RUNNING
            job.actual_device.current_job = job
            job.actual_device.save()
        job.start_time = datetime.datetime.utcnow()
        shutil.rmtree(job.output_dir, ignore_errors=True)
        job.log_file.save('job-%s.log' % job.id, ContentFile(''), save=False)
        job.save()
        json_data = self._get_json_data(job)
        transaction.commit()
        return json_data

    def getJobDetails(self, job):
        return self.deferForDB(self.getJobDetails_impl, job)

    def getOutputDirForJobOnBoard_impl(self, board_name):
        device = Device.objects.get(hostname=board_name)
        job = device.current_job
        return job.output_dir

    def getOutputDirForJobOnBoard(self, board_name):
        return self.deferForDB(self.getOutputDirForJobOnBoard_impl, board_name)

    def jobCompleted_impl(self, board_name, exit_code, kill_reason):
        self.logger.debug('marking job as complete on %s', board_name)
        device = Device.objects.get(hostname=board_name)
        old_device_status = device.status
        if device.status == Device.RUNNING:
            device.status = Device.IDLE
        elif device.status == Device.OFFLINING:
            device.status = Device.OFFLINE
        elif device.status == Device.RESERVED:
            device.status = Device.IDLE
        else:
            self.logger.error(
                "Unexpected device state in jobCompleted: %s" % device.status)
            device.status = Device.IDLE
        job = device.current_job
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
        DeviceStateTransition.objects.create(
            created_by=None, device=device, old_state=old_device_status,
            new_state=device.status, message=None, job=job).save()

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
        token.delete()
        try:
            job.send_summary_mails()
        except:
            # Better to catch all exceptions here and log it than have this
            # method fail.
            self.logger.exception(
                'sending job summary mails for job %r failed', job.pk)
        transaction.commit()

    def jobCompleted(self, board_name, exit_code, kill_reason):
        return self.deferForDB(self.jobCompleted_impl, board_name, exit_code, kill_reason)

    def jobCheckForCancellation_impl(self, board_name):
        device = Device.objects.get(hostname=board_name)
        job = device.current_job
        return job.status != TestJob.RUNNING

    def jobCheckForCancellation(self, board_name):
        return self.deferForDB(self.jobCheckForCancellation_impl, board_name)


def _get_device_version(bundle):
    if bundle is None:
        return None
    try:
        lava_test_run = bundle.test_runs.filter(test__test_id='lava')[0]
        version_attribute = lava_test_run.attributes.filter(name='target.device_version')[0]
        return version_attribute.value
    except IndexError:
        return 'unknown'
