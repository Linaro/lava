from contextlib import contextmanager
import datetime
import os
from django_testscenarios.ubertest import TestCase

from lava_scheduler_app.models import (
    Device,
    DeviceType,
    TestJob,
    Tag,
    DevicesUnavailableException,
)
from lava_scheduler_app.tests.test_submission import TestCaseWithFactory
from lava_scheduler_daemon.dbjobsource import DatabaseJobSource, find_device_for_job
from lava_scheduler_daemon.tests.base import DatabaseJobSourceTestEngine


class DatabaseJobTest(DatabaseJobSourceTestEngine):

    def setUp(self):
        super(DatabaseJobTest, self).setUp()

        DeviceType.objects.all().delete()

        self.panda_type = self.factory.ensure_device_type(name='panda')

        # make sure the DB is in a clean state wrt devices and jobs
        Device.objects.all().delete()
        TestJob.objects.all().delete()
        Tag.objects.all().delete()

        panda_type = self.panda_type
        # prevent local variables - get changes from the database
        self.factory.make_device(device_type=panda_type, hostname='panda01')
        self.factory.make_device(device_type=panda_type, hostname='panda02')
        self.factory.make_device(device_type=panda_type, hostname='panda03')
        self.factory.make_device(device_type=panda_type, hostname='panda04')
        self.factory.make_device(device_type=panda_type, hostname='panda05')
        self.factory.make_device(device_type=panda_type, hostname='panda06')

        self.user = self.factory.make_user()

        self.master = DatabaseJobSource(lambda: ['panda01', 'panda02'])

    def test_previous_state(self):
        """
        Test behaviour when a health check completes
        """
        self.report_start(self.whoami())

        Device.objects.get(hostname='panda01').state_transition_to(Device.OFFLINE)

        # set a series of previous transitions for panda02
        Device.objects.get(hostname='panda02').state_transition_to(Device.OFFLINE)
        Device.objects.get(hostname='panda02').state_transition_to(Device.IDLE)
        Device.objects.get(hostname='panda02').state_transition_to(Device.RESERVED)
        Device.objects.get(hostname='panda02').state_transition_to(Device.RUNNING)
        Device.objects.get(hostname='panda02').state_transition_to(Device.IDLE)
        Device.objects.get(hostname='panda02').state_transition_to(Device.OFFLINE)
        Device.objects.get(hostname='panda02').state_transition_to(Device.IDLE)

        Device.objects.get(hostname='panda03').state_transition_to(Device.RUNNING)
        Device.objects.get(hostname='panda04').state_transition_to(Device.RESERVED)
        Device.objects.get(hostname='panda05').state_transition_to(Device.RETIRED)
        Device.objects.get(hostname='panda06').state_transition_to(Device.OFFLINING)

        self.panda_type.health_check_job = self.factory.make_job_json(health_check='true')
        self.panda_type.save()

        jobs = self.scheduler_tick()

        self.assertEqual(len(jobs), 1)
        job = TestJob.objects.get(id=jobs[0].id)
        job_id = job.id
        self.assertEqual(job.status, TestJob.RUNNING)

        for job in jobs:
            job_obj = TestJob.objects.get(pk=job.id)  # reload
            job_obj.status = TestJob.COMPLETE
            self.job_finished(job_obj)

        self.assertEqual(len(jobs), 1)
        job = TestJob.objects.get(id=job_id)
        self.assertEqual(job.status, TestJob.COMPLETE)

        self.assertEqual(
            Device.objects.get(hostname='panda02').status,
            Device.IDLE
        )

        self.assertEqual(
            Device.objects.get(hostname='panda02').health_status,
            Device.HEALTH_PASS
        )

        self.assertEqual(
            Device.objects.get(hostname='panda01').health_status,
            Device.HEALTH_UNKNOWN
        )

        panda01 = Device.objects.get(hostname='panda01')
        panda01.status = Device.IDLE
        panda01.save()

        jobs = self.scheduler_tick()

        self.assertEqual(
            Device.objects.get(hostname='panda01').health_status,
            Device.HEALTH_UNKNOWN
        )

        self.assertEqual(Device.objects.get(hostname='panda01').status, Device.RUNNING)

        for job in jobs:
            job_obj = TestJob.objects.get(pk=job.id)  # reload
            job_obj.status = TestJob.COMPLETE
            self.job_finished(job_obj)

        self.assertEqual(Device.objects.get(hostname='panda01').status, Device.IDLE)
        self.assertIsNone(Device.objects.get(hostname='panda01').current_job)
        self.assertEqual(
            Device.objects.get(hostname='panda01').health_status,
            Device.HEALTH_PASS
        )
        self.scheduler_tick()
        self.assertEqual(Device.objects.get(hostname='panda01').status, Device.IDLE)
        self.assertIsNone(Device.objects.get(hostname='panda01').current_job)
        self.assertEqual(
            Device.objects.get(hostname='panda01').health_status,
            Device.HEALTH_PASS
        )

        self.cleanup(self.whoami())

    def test_submitted_job(self):
        self.report_start(self.whoami())

        Device.objects.get(hostname='panda01').state_transition_to(Device.OFFLINE)
        Device.objects.get(hostname='panda01').state_transition_to(Device.IDLE)
        Device.objects.get(hostname='panda01').state_transition_to(Device.RESERVED)
        Device.objects.get(hostname='panda01').state_transition_to(Device.RUNNING)
        Device.objects.get(hostname='panda01').state_transition_to(Device.IDLE)

        Device.objects.get(hostname='panda02').state_transition_to(Device.RETIRED)
        Device.objects.get(hostname='panda03').state_transition_to(Device.RETIRED)
        Device.objects.get(hostname='panda04').state_transition_to(Device.RETIRED)
        Device.objects.get(hostname='panda05').state_transition_to(Device.RETIRED)
        Device.objects.get(hostname='panda06').state_transition_to(Device.RETIRED)

        self.panda_type.health_check_job = self.factory.make_job_json(health_check='true')
        self.panda_type.save()

        jobs = self.scheduler_tick()

        for job in jobs:
            job_obj = TestJob.objects.get(pk=job.id)  # reload
            job_obj.status = TestJob.COMPLETE
            self.job_finished(job_obj)

        jobs = self.scheduler_tick()
        self.submit_job()

        for job in jobs:
            job_obj = TestJob.objects.get(pk=job.id)  # reload
            job_obj.status = TestJob.COMPLETE
            self.job_finished(job_obj)

        jobs = self.scheduler_tick()
        self.submit_job()

        for job in jobs:
            job_obj = TestJob.objects.get(pk=job.id)  # reload
            job_obj.status = TestJob.COMPLETE
            self.job_finished(job_obj)

        self.cleanup(self.whoami())

    def test_stale_job_failure(self):
        """
        Test behaviour if test completion not stored as a single operation
        """
        self.report_start(self.whoami())

        self.panda_type.health_check_job = self.factory.make_job_json(health_check='true')
        self.panda_type.save()

        Device.objects.get(hostname='panda01').state_transition_to(Device.OFFLINE)
        Device.objects.get(hostname='panda02').state_transition_to(Device.IDLE)
        Device.objects.get(hostname='panda03').state_transition_to(Device.RUNNING)
        Device.objects.get(hostname='panda04').state_transition_to(Device.RESERVED)
        Device.objects.get(hostname='panda05').state_transition_to(Device.RETIRED)
        Device.objects.get(hostname='panda06').state_transition_to(Device.OFFLINING)

        job = self.submit_job()
        job.status = TestJob.RUNNING
        job.save()
        job_id = job.id

        job = TestJob.objects.get(id=job_id)
        self.assertEqual(job.requested_device_type.name, self.panda_type.name)
        self.assertEqual(job.status, TestJob.RUNNING)

        panda01 = Device.objects.get(hostname='panda01')
        self.assertEqual(panda01.health_status, Device.HEALTH_UNKNOWN)
        # set a side-effect of a broken state
        panda01.current_job = job
        panda01.save()
        panda01 = Device.objects.get(hostname='panda01')
        self.assertEqual(panda01.current_job, job)
        self.assertEqual(panda01.status, Device.OFFLINE)
        self.assertEqual(panda01.health_status, Device.HEALTH_UNKNOWN)

        panda02 = Device.objects.get(hostname='panda02')
        self.assertEqual(panda02.current_job, None)
        self.assertEqual(panda02.status, Device.IDLE)
        self.assertEqual(panda02.health_status, Device.HEALTH_UNKNOWN)

        panda03 = Device.objects.get(hostname='panda03')
        panda03.health_status = Device.HEALTH_PASS
        panda03.save()
        panda03 = Device.objects.get(hostname='panda03')
        self.assertEqual(panda03.health_status, Device.HEALTH_PASS)

        panda04 = Device.objects.get(hostname='panda04')
        panda04.health_status = Device.HEALTH_FAIL
        panda04.save()
        panda04 = Device.objects.get(hostname='panda04')
        self.assertEqual(panda04.health_status, Device.HEALTH_FAIL)

        self.assertEqual(
            Device.objects.get(hostname='panda05').health_status,
            Device.HEALTH_UNKNOWN)
        self.assertEqual(
            Device.objects.get(hostname='panda06').health_status,
            Device.HEALTH_UNKNOWN)

        jobs = self.scheduler_tick()

        self.assertEqual(len(jobs), 1)
        job = TestJob.objects.get(id=job_id)
        self.assertEqual(job.status, TestJob.RUNNING)

        for job in jobs:
            job_obj = TestJob.objects.get(pk=job.id)  # reload
            job_obj.status = TestJob.COMPLETE
            self.job_finished(job_obj)

        self.assertEqual(len(jobs), 1)
        job = TestJob.objects.get(id=job_id)
        self.assertEqual(job.status, TestJob.RUNNING)

        panda01 = Device.objects.get(hostname='panda01')
        panda02 = Device.objects.get(hostname='panda02')
        panda03 = Device.objects.get(hostname='panda03')
        panda04 = Device.objects.get(hostname='panda04')
        panda05 = Device.objects.get(hostname='panda05')
        panda06 = Device.objects.get(hostname='panda06')

        self.assertIsNone(panda02.current_job)
        self.assertEqual(panda02.status, Device.IDLE)

        self.assertEqual(panda01.status, Device.OFFLINE)
        self.assertEqual(panda02.status, Device.IDLE)
        self.assertEqual(panda03.status, Device.RUNNING)
        self.assertEqual(panda04.status, Device.RESERVED)
        self.assertEqual(panda05.status, Device.RETIRED)
        self.assertEqual(panda06.status, Device.OFFLINING)

        jobs = self.scheduler_tick()

        self.assertEqual(len(jobs), 0)

        self.assertIsNone(Device.objects.get(hostname='panda02').current_job)

        jobs = self.scheduler_tick()
        for job in jobs:
            job_obj = TestJob.objects.get(pk=job.id)  # reload
            job_obj.status = TestJob.COMPLETE
            self.job_finished(job_obj)

        self.assertEqual(len(jobs), 0)

        jobs = self.scheduler_tick()

        self.assertEqual(len(jobs), 0)

        panda02 = Device.objects.get(hostname='panda02')

        # FIXME: this is actually a bug and will need an update when the bug is fixed.
        self.assertEqual(panda01.current_job.id, job_id)

        self.assertEqual(panda02.current_job, None)
        self.assertEqual(panda02.status, Device.IDLE)
        self.assertEqual(panda02.health_status, Device.HEALTH_PASS)

        panda01 = Device.objects.get(hostname='panda01')
        self.assertEqual(panda01.status, Device.OFFLINE)
        self.assertEqual(panda01.health_status, Device.HEALTH_UNKNOWN)

        panda03 = Device.objects.get(hostname='panda03')
        self.assertEqual(panda03.health_status, Device.HEALTH_PASS)
        self.assertEqual(panda03.status, Device.RUNNING)

        panda04 = Device.objects.get(hostname='panda04')
        self.assertEqual(panda04.status, Device.RESERVED)
        self.assertEqual(panda04.health_status, Device.HEALTH_FAIL)

        panda05 = Device.objects.get(hostname='panda05')
        self.assertEqual(panda05.status, Device.RETIRED)
        self.assertEqual(panda05.health_status, Device.HEALTH_UNKNOWN)

        panda06 = Device.objects.get(hostname='panda06')
        self.assertEqual(panda06.status, Device.OFFLINING)
        self.assertEqual(panda06.health_status, Device.HEALTH_UNKNOWN)

        self.cleanup(self.whoami())
