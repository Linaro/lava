import logging
from lava_scheduler_app.models import (
    Device,
    DeviceType,
    TestJob,
    Tag,
)
from lava_scheduler_daemon.dbjobsource import DatabaseJobSource
from lava_scheduler_daemon.tests.base import DatabaseJobSourceTestEngine


class DatabaseJobTest(DatabaseJobSourceTestEngine):

    def setUp(self):
        super(DatabaseJobTest, self).setUp()
        logger = logging.getLogger('lava_scheduler_daemon.dbjobsource.DatabaseJobSource')
        logger.disabled = True
        logger = logging.getLogger('dispatcher-master')
        logger.disabled = True
        logger = logging.getLogger('lava_scheduler_app')
        logger.disabled = True

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
