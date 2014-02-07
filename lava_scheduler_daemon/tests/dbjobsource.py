from contextlib import contextmanager
import datetime
import os

from django_testscenarios.ubertest import TestCase

from lava_scheduler_app.models import Device, DeviceType, TestJob
from lava_scheduler_app.tests.submission import TestCaseWithFactory
from lava_scheduler_daemon.dbjobsource import DatabaseJobSource, find_device_for_job


def make_job(requested_device_type, requested_device):
    return FindDeviceForJobTest.Job(requested_device_type, requested_device)


def make_device(hostname, device_type=None):
    return FindDeviceForJobTest.Device(hostname, device_type)


def make_device_type(device_type):
    return FindDeviceForJobTest.DeviceType(device_type)


class FindDeviceForJobTest(TestCase):

    class Job(object):

        def __init__(self, requested_device_type, requested_device):
            self.requested_device_type = make_device_type(requested_device_type)
            self.requested_device = make_device(requested_device)
            self.submitter = None  # FIXME

    class DeviceType(object):

        def __init__(self, name):
            self.name = name

        def __eq__(self, other):
            return self.name == other.name

        def __repr__(self):
            return self.name

    class Device(object):

        def __init__(self, name, device_type=None):
            self.name = name
            self.device_type = device_type and FindDeviceForJobTest.DeviceType(device_type)

        def __eq__(self, other):
            return self.name == other.name

        def __repr__(self):
            return "/".join([self.name, repr(self.device_type)])

        def can_submit(self, user):
            return True  # TODO

    def test_requested_device(self):
        """
        tests that find_device_for_job gives preference to matching by requested
        _device_ over matching by requested device _type_.
        """
        job = make_job('panda', 'panda01')
        devices = [make_device('panda02', 'panda'), make_device('panda01', 'panda')]
        chosen_device = find_device_for_job(job, devices)
        self.assertEqual(devices[1], chosen_device)


class DatabaseJobSourceTest(TestCaseWithFactory):

    def setUp(self):
        super(DatabaseJobSourceTest, self).setUp()

        DeviceType.objects.all().delete()

        self.panda = self.factory.ensure_device_type(name='panda')
        self.arndale = self.factory.ensure_device_type(name='arndale')

        # make sure the DB is in a clean state wrt devices and jobs
        Device.objects.all().delete()
        TestJob.objects.all().delete()

        panda = self.panda
        self.panda01 = self.factory.make_device(device_type=panda, hostname='panda01')
        self.panda02 = self.factory.make_device(device_type=panda, hostname='panda02')

        arndale = self.arndale
        self.arndale01 = self.factory.make_device(device_type=arndale, hostname='arndale01')
        self.arndale02 = self.factory.make_device(device_type=arndale, hostname='arndale02')

        self.user = self.factory.make_user()

        self.master = DatabaseJobSource(lambda: ['panda01', 'panda02'])

    def submit_job(self, **kw):
        job_definition = self.factory.make_job_json(**kw)
        return TestJob.from_json_and_user(job_definition, self.user)

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

    def job_finished(self, job, worker=None):
        if worker is None:
            worker = self.master
        with self.log_scheduler_state("job %d completes" % job.id):
            worker.jobCompleted_impl(job.actual_device.hostname, 0, None)

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

    def test_simple_multi_node_scheduler(self):
        submitted_jobs = self.submit_job(
            device_group=[
                {"device_type": "panda", "count": 1, "role": "client"},
                {"device_type": "panda", "count": 1, "role": "server"},
            ]
        )

        scheduled_jobs = self.scheduler_tick()

        self.assertEqual(submitted_jobs, scheduled_jobs)

    def test_single_node_and_multinode(self):
        singlenode_job1 = self.submit_job(device_type='panda')
        singlenode_job2 = self.submit_job(device_type='panda')

        self.scheduler_tick()  # should schedule single node jobs and start running them

        singlenode_job1 = TestJob.objects.get(pk=singlenode_job1.id)  # reload
        singlenode_job2 = TestJob.objects.get(pk=singlenode_job2.id)  # reload

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

    def test_health_check(self):

        self.panda.health_check_job = self.factory.make_job_json(health_check='true')
        self.panda.save()

        jobs = self.scheduler_tick()

        panda_jobs = [j for j in jobs if j.actual_device.device_type == self.panda]

        self.assertTrue(len(panda_jobs) > 0)
        self.assertTrue(all([job.actual_device is not None for job in panda_jobs]))

    def test_one_worker_does_not_mess_with_jobs_from_the_others(self):
        # simulate a worker with no devices configured
        worker = DatabaseJobSource(lambda: [])

        self.submit_job(device_type='panda')

        scheduled_jobs = self.scheduler_tick(worker)

        self.assertEqual([], scheduled_jobs)
        self.assertTrue(all([job.status == TestJob.SUBMITTED for job in TestJob.objects.all()]))

    def test_multinode_job_across_different_workers(self):
        master = self.master
        worker = DatabaseJobSource(lambda: ['arndale01'])
        arndale01 = self.arndale01
        self.panda02.state_transition_to(Device.OFFLINE)
        panda01 = self.panda01

        self.submit_job(
            device_group=[
                {"device_type": "panda", "count": 1, "role": "client"},
                {"device_type": "arndale", "count": 1, "role": "server"},
            ]
        )

        master_jobs = self.scheduler_tick(master)
        worker_jobs = self.scheduler_tick(worker)

        self.assertEqual(1, len(master_jobs))
        self.assertEqual(master_jobs[0].actual_device, panda01)

        self.assertEqual(1, len(worker_jobs))
        self.assertEqual(worker_jobs[0].actual_device, arndale01)

    def test_two_multinode_jobs_plus_two_singlenode_jobs(self):

        single1 = self.submit_job(device_type='panda')
        single2 = self.submit_job(device_type='panda')

        multi1a, multi1b = self.submit_job(
            device_group=[
                {"device_type": "panda", "count": 1, "role": "client"},
                {"device_type": "panda", "count": 1, "role": "server"},
            ]
        )

        multi2a, multi2b = self.submit_job(
            device_group=[
                {"device_type": "panda", "count": 1, "role": "client"},
                {"device_type": "panda", "count": 1, "role": "server"},
            ]
        )

        # make it confusing by making both multinode jobs have the exact same
        # submit time
        # also set the target_group string to make the outcome predictable
        now = datetime.datetime.now()
        for job in [multi1a, multi1b]:
            job.submit_time = now
            job.target_group = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
            job.save()
        for job in [multi2a, multi2b]:
            job.submit_time = now
            job.target_group = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
            job.save()

        scheduled = sorted(self.scheduler_tick(), key=lambda job: job.id)
        self.assertEqual([single1, single2], scheduled)
        single1, single2 = scheduled  # reload locals

        self.job_finished(single1)

        self.assertEqual([], self.scheduler_tick())

        self.job_finished(single2)

        scheduled = sorted(self.scheduler_tick(), key=lambda job: job.id)
        self.assertEqual([multi1a, multi1b], scheduled)

    def test_two_multinode_and_multiworker_jobs_waiting_in_the_queue(self):
        master = self.master
        worker = DatabaseJobSource(lambda: ['arndale01', 'arndale02'])

        self.submit_job(device_type='panda')
        self.submit_job(device_type='panda')
        self.submit_job(device_type='arndale')
        self.submit_job(device_type='arndale')

        p1, p2 = self.scheduler_tick(master)
        a1, a2 = self.scheduler_tick(worker)

        m1p, m1a = self.submit_job(
            device_group=[
                {"device_type": "panda", "count": 1, "role": "client"},
                {"device_type": "arndale", "count": 1, "role": "server"},
            ]
        )
        m1p.target_group = m1a.target_group = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
        m1p.save()
        m1a.save()
        m2p, m2a = self.submit_job(
            device_group=[
                {"device_type": "panda", "count": 1, "role": "client"},
                {"device_type": "arndale", "count": 1, "role": "server"},
            ]
        )
        m2p.target_group = m2a.target_group = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
        m2p.save()
        m2a.save()

        self.assertEqual([], self.scheduler_tick(master))
        self.assertEqual([], self.scheduler_tick(worker))

        self.job_finished(p1, master)
        self.job_finished(a1, worker)

        self.assertEqual([m1p], self.scheduler_tick(master))
        self.assertEqual([m1a], self.scheduler_tick(worker))
