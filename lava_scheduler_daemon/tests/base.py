import os
import traceback
from contextlib import contextmanager
from lava_scheduler_app.tests.test_submission import TestCaseWithFactory
from lava_scheduler_app.models import (
    Device,
    TestJob,
    Tag,
)

# pylint: disable=attribute-defined-outside-init,superfluous-parens,too-many-ancestors,no-self-use,no-member
# pylint: disable=invalid-name,too-few-public-methods,too-many-statements,unbalanced-tuple-unpacking
# pylint: disable=protected-access,too-many-public-methods,unpacking-non-sequence


class DatabaseJobSourceTestEngine(TestCaseWithFactory):

    # noinspection PyPep8Naming
    def setUp(self):
        super(DatabaseJobSourceTestEngine, self).setUp()
        self.restart(self.whoami())

    def restart(self, who):
        pass

    def whoami(self):
        """
        Declare the function name - call directly in the function reporting status
        """
        stack = traceback.extract_stack()
        if stack:
            return stack[-2][2]
        return 'unknown'

    def report_start(self, who):
        """
        In DEBUG, the start and end of a test case is not obvious
        """
        if 'DEBUG' in os.environ:
            print "====== starting %s ==========" % who

    def report_status(self, status, who):
        """
        Use to clarify the expected results or actions when viewing debug output
        State what has been done between the last tick and the next tick
        :param status: message about test actions
        :param who: self.whoami()
        """
        if 'DEBUG' in os.environ:
            print "====== %s %s ==========" % (status, who)

    def report_end(self, who):
        if 'DEBUG' in os.environ:
            print "====== finishing %s ==========" % who

    def cleanup(self, who):
        self.report_end(who)
        # make sure the DB is in a clean state wrt devices and jobs
        Device.objects.all().delete()
        TestJob.objects.all().delete()
        Tag.objects.all().delete()

    def submit_job(self, **kw):
        job_definition = self.factory.make_job_json(**kw)
        return TestJob.from_json_and_user(job_definition, self.user)

    # noinspection PyProtectedMember
    @contextmanager
    def log_scheduler_state(self, event):
        if 'DEBUG' in os.environ:
            print("##############################################")
            print('# Before %s' % event)
            print('        Job queue: %r' % self.master._get_job_queue())
            print('Available devices: %r' % self.master._get_available_devices())
        yield
        if 'DEBUG' in os.environ:
            print('# After %s' % event)
            print('        Job queue: %r' % self.master._get_job_queue())
            print('Available devices: %r' % self.master._get_available_devices())

    def scheduler_tick(self, worker=None):
        if worker is None:
            worker = self.master
        with self.log_scheduler_state("scheduler ticks"):
            jobs = worker.getJobList_impl()
        if 'DEBUG' in os.environ:
            print('Jobs ready to run: %r' % jobs)
            print('   Submitted jobs: %r' % TestJob.objects.filter(status=TestJob.SUBMITTED))
            print('     Running jobs: %r' % TestJob.objects.filter(status=TestJob.RUNNING))
            print(' State of devices: %r' % Device.objects.all())
        for job in jobs:
            # simulates the actual daemon, which will start jobs just after it
            # gets them from the scheduler
            self.job_started(job, worker)
        return jobs

    def job_started(self, job, worker=None):
        if worker is None:
            worker = self.master
        worker.jobStarted_impl(job)

    def job_failed(self, job, worker=None):
        if worker is None:
            worker = self.master
        with self.log_scheduler_state("job %d completes" % job.id):
            worker.jobCompleted_impl(job.id, job.actual_device.hostname, 1,
                                     None)

    def job_finished(self, job, worker=None):
        if worker is None:
            worker = self.master
        with self.log_scheduler_state("job %d completes" % job.id):
            worker.jobCompleted_impl(job.id, job.actual_device.hostname, 0,
                                     None)

    def device_status(self, hostname, status=None, health_status=None):
        device = Device.objects.get(pk=hostname)
        if status is not None:
            device.status = status
        if health_status is not None:
            device.health_status = health_status
        device.save()
