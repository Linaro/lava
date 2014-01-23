from contextlib import contextmanager
import os

from django_testscenarios.ubertest import TestCase

from lava_scheduler_app.models import Device, DeviceType, TestJob
from lava_scheduler_app.tests.submission import TestCaseWithFactory
from lava_scheduler_daemon.dbjobsource import DatabaseJobSource


class DatabaseJobSourceTest(TestCaseWithFactory):

    def setUp(self):
        super(DatabaseJobSourceTest, self).setUp()

        self.panda = self.factory.ensure_device_type(name='panda')

        # make sure the DB is in a clean state wrt devices and jobs
        Device.objects.all().delete()
        TestJob.objects.all().delete()

        panda = self.panda
        self.panda01 = self.factory.make_device(device_type=panda, hostname='panda01')
        self.panda02 = self.factory.make_device(device_type=panda, hostname='panda02')

        self.user = self.factory.make_user()

        self.source = DatabaseJobSource()

    def submit_job(self, **kw):
        job_definition = self.factory.make_job_json(**kw)
        return TestJob.from_json_and_user(job_definition, self.user)

    @contextmanager
    def log_scheduler_state(self, event):
        if 'DEBUG' in os.environ:
            print("##############################################")
            print('# Before %s' % event)
            print('        Job queue: %r' % self.source._get_job_queue())
            print('Available devices: %r' % self.source._get_available_devices())
        yield
        if 'DEBUG' in os.environ:
            print('# After %s' % event)
            print('        Job queue: %r' % self.source._get_job_queue())
            print('Available devices: %r' % self.source._get_available_devices())
            print('')

    def scheduler_tick(self):
        with self.log_scheduler_state("scheduler ticks"):
            jobs = self.source.getJobList_impl()
        return jobs

    def job_finished(self, job):
        with self.log_scheduler_state("job %d completes" % job.id):
            self.source.jobCompleted_impl(job.actual_device.hostname, 0, None)

    def device_status(self, hostname, status, health_status=None):
        device = Device.objects.get(pk=hostname)
        device.status = status
        if health_status:
            device.health_status = health_status
        device.save()

    def test_simple_single_node_scheduling(self):
        submitted = self.submit_job(device_type='panda')
        scheduled = self.scheduler_tick()

        self.assertEqual([submitted], scheduled)
        job = scheduled[0]
        self.assertTrue(job.actual_device)
        self.assertEqual(job.status, TestJob.RUNNING)

    def test_simple_multi_node_scheduler(self):
        submitted_jobs = self.submit_job(
            device_group=[
                {"device_type": "panda", "count": 1, "role": "client"},
                {"device_type": "panda", "count": 1, "role": "server"},
            ]
        )

        scheduled_jobs = self.scheduler_tick()

        self.assertEqual(submitted_jobs, scheduled_jobs)
        self.assertTrue(all([j.status == TestJob.RUNNING for j in scheduled_jobs]))

    def test_single_node_and_multinode(self):
        singlenode_job1 = self.submit_job(device_type='panda')
        singlenode_job2 = self.submit_job(device_type='panda')

        self.scheduler_tick()  # should schedule single node jobs

        singlenode_job1 = TestJob.objects.get(pk=singlenode_job1.id)  # reload
        singlenode_job2 = TestJob.objects.get(pk=singlenode_job2.id)  # reload
        self.assertEqual(singlenode_job1.status, TestJob.RUNNING)
        self.assertEqual(singlenode_job2.status, TestJob.RUNNING)

        # multinode jobs submitted
        multinode_job1, multinode_job2 = self.submit_job(
            device_group=[
                {"device_type": "panda", "count": 1, "role": "client"},
                {"device_type": "panda", "count": 1, "role": "server"},
            ]
        )

        # job on first device finishes
        self.job_finished(singlenode_job1)
        singlenode_job1 = TestJob.objects.get(pk=singlenode_job1.id)  # reload
        self.assertEqual(singlenode_job1.status, TestJob.COMPLETE)

        self.scheduler_tick()  # should reserve a device for one of jobs in the multinode group

        # one (and only one) of the multinode jobs gets a device assigned
        multinode_job1 = TestJob.objects.get(pk=multinode_job1.id)  # reload
        multinode_job2 = TestJob.objects.get(pk=multinode_job2.id)  # reload
        self.assertTrue(any([job.actual_device is not None for job in [multinode_job1, multinode_job2]]))
        self.assertTrue(any([job.actual_device is None for job in [multinode_job1, multinode_job2]]))

        # job on second board finishes
        self.job_finished(singlenode_job2)
        singlenode_job2 = TestJob.objects.get(pk=singlenode_job2.id)  # reload
        self.assertEqual(singlenode_job2.status, TestJob.COMPLETE)

        self.scheduler_tick()  # should reserve a device for the other jon in the multinode job

        multinode_job1 = TestJob.objects.get(pk=multinode_job1.id)  # reload
        multinode_job2 = TestJob.objects.get(pk=multinode_job2.id)  # reload
        self.assertTrue(all([job.actual_device is not None for job in [multinode_job1, multinode_job2]]))
        self.assertTrue(all([job.status == TestJob.RUNNING for job in [multinode_job1, multinode_job2]]))
