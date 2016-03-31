import glob
import unittest
from lava_scheduler_app.dbutils import (
    create_job,
    select_device,
)
from lava_scheduler_app.tests.test_pipeline import YamlFactory, TestCaseWithFactory
from lava_scheduler_app.utils import (
    jinja_template_path,
)
from lava_scheduler_app.models import (
    Device,
    Tag,
    DeviceDictionary,
    TestJob,
    Worker
)


class MasterTest(TestCaseWithFactory):  # pylint: disable=too-many-ancestors

    def setUp(self):
        super(MasterTest, self).setUp()
        self.factory = YamlFactory()
        jinja_template_path(system=False)
        self.device_type = self.factory.make_device_type()
        self.conf = {
            'arch': 'amd64',
            'extends': 'qemu.jinja2',
            'mac_addr': '52:54:00:12:34:59',
            'memory': '256',
        }
        self.worker, _ = Worker.objects.get_or_create(hostname='localhost')
        self.remote, _ = Worker.objects.get_or_create(hostname='remote')
        # exclude remote from the list
        self.dispatchers = [self.worker.hostname]

    def restart(self):  # pylint: disable=no-self-use
        # make sure the DB is in a clean state wrt devices and jobs
        Device.objects.all().delete()  # pylint: disable=no-member
        TestJob.objects.all().delete()  # pylint: disable=no-member
        Tag.objects.all().delete()

    @unittest.skipIf(len(glob.glob('/sys/block/loop*')) <= 0, "loopback support not found")
    def test_select_device(self):
        self.restart()
        hostname = 'fakeqemu3'
        device_dict = DeviceDictionary(hostname=hostname)
        device_dict.parameters = self.conf
        device_dict.save()
        device = self.factory.make_device(self.device_type, hostname)
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(),
            self.factory.make_user())
        selected = select_device(job, self.dispatchers)
        self.assertIsNone(selected)
        job.actual_device = device
        selected = select_device(job, self.dispatchers)
        self.assertIsNone(selected)
        device.worker_host = self.worker
        selected = select_device(job, self.dispatchers)
        self.assertIsNone(selected)
        # device needs to be in reserved state
        # fake up the assignment which needs a separate test
        job.actual_device = device
        job.save()
        device.current_job = job
        device.status = Device.RESERVED
        device.save()
        selected = select_device(job, self.dispatchers)
        self.assertEqual(selected, device)
        # print(selected)  # pylint: disable=superfluous-parens

    @unittest.skipIf(len(glob.glob('/sys/block/loop*')) <= 0, "loopback support not found")
    def test_job_handlers(self):
        self.restart()
        hostname = 'fakeqemu3'
        device_dict = DeviceDictionary(hostname=hostname)
        device_dict.parameters = self.conf
        device_dict.save()
        device = self.factory.make_device(self.device_type, hostname)
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(),
            self.factory.make_user())
        selected = select_device(job, self.dispatchers)
        self.assertIsNone(selected)
        job.actual_device = device
        selected = select_device(job, self.dispatchers)
        self.assertIsNone(selected)
        device.worker_host = self.worker
        selected = select_device(job, self.dispatchers)
        self.assertIsNone(selected)
        create_job(job, device)
        self.assertEqual(job.actual_device, device)
        self.assertEqual(device.status, Device.RESERVED)

    @unittest.skipIf(len(glob.glob('/sys/block/loop*')) <= 0, "loopback support not found")
    def test_dispatcher_restart(self):
        self.restart()
        hostname = 'fakeqemu4'
        device_dict = DeviceDictionary(hostname=hostname)
        device_dict.parameters = self.conf
        device_dict.save()
        device = self.factory.make_device(self.device_type, hostname)
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(),
            self.factory.make_user())
        job.actual_device = device
        self.assertEqual(job.status, TestJob.SUBMITTED)
        device.worker_host = self.remote
        selected = select_device(job, self.dispatchers)
        self.assertIsNone(selected)
        self.assertEqual(job.status, TestJob.SUBMITTED)
        create_job(job, device)
        self.assertEqual(job.actual_device, device)
        self.assertEqual(device.status, Device.RESERVED)
        selected = select_device(job, self.dispatchers)
        self.assertIsNone(selected)
        self.assertEqual(job.status, TestJob.SUBMITTED)
