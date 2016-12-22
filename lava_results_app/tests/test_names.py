import os
import yaml
import logging
from django.contrib.auth.models import User
from django.core.validators import URLValidator
from lava_results_app.models import (
    TestCase, TestSuite
)
from lava_results_app.dbutils import map_scanned_results
from lava_scheduler_app.models import (
    TestJob, Device,
    DeviceType, DeviceDictionary,
    JobPipeline,
)
from django_testscenarios.ubertest import TestCase as DjangoTestCase

# note: when creating extensions, ensure a urls.py and views.py exist

# pylint: disable=invalid-name,too-few-public-methods


class ModelFactory(object):

    def __init__(self):
        self._int = 0

    def getUniqueInteger(self):
        self._int += 1
        return self._int

    def getUniqueString(self, prefix='generic'):
        return '%s-%d' % (prefix, self.getUniqueInteger())

    def get_unique_user(self, prefix='generic'):
        return "%s-%d" % (prefix, User.objects.count() + 1)

    def cleanup(self):
        DeviceType.objects.all().delete()
        # make sure the DB is in a clean state wrt devices and jobs
        Device.objects.all().delete()
        TestJob.objects.all().delete()
        [item.delete() for item in DeviceDictionary.object_list()]
        User.objects.all().delete()

    def make_user(self):
        return User.objects.create_user(
            self.get_unique_user(),
            '%s@mail.invalid' % (self.getUniqueString(),),
            self.getUniqueString())

    def make_job_data(self, actions=None, **kw):
        sample_job_file = os.path.join(os.path.dirname(__file__), 'qemu.yaml')
        with open(sample_job_file, 'r') as test_support:
            data = yaml.load(test_support)
        data.update(kw)
        return data

    def make_job_yaml(self, **kw):
        return yaml.safe_dump(self.make_job_data(**kw))

    def make_fake_qemu_device(self, hostname='fakeqemu1'):  # pylint: disable=no-self-use
        qemu = DeviceDictionary(hostname=hostname)
        qemu.parameters = {'extends': 'qemu.jinja2', 'arch': 'amd64'}
        qemu.save()

    def make_device_type(self, name='qemu', health_check_job=None):
        (device_type, created) = DeviceType.objects.get_or_create(
            name=name, health_check_job=health_check_job)
        if created:
            device_type.save()
        return device_type

    def make_device(self, device_type=None, hostname=None, tags=None, is_public=True, **kw):
        if device_type is None:
            device_type = self.make_device_type()
        if hostname is None:
            hostname = self.getUniqueString()
        if tags and type(tags) != list:
            tags = []
        device = Device(device_type=device_type, is_public=is_public, hostname=hostname, is_pipeline=True, **kw)
        self.make_fake_qemu_device(hostname)
        if tags:
            device.tags = tags
        logging.debug("making a device of type %s %s %s with tags '%s'"
                      % (device_type, device.is_public, device.hostname, ", ".join([x.name for x in device.tags.all()])))
        device.save()
        return device


class TestCaseWithFactory(DjangoTestCase):

    # noinspection PyPep8Naming
    def setUp(self):
        DjangoTestCase.setUp(self)
        self.factory = ModelFactory()
        self.device_type = self.factory.make_device_type()
        self.factory.make_device(device_type=self.device_type, hostname="fakeqemu1")
        self.user = self.factory.make_user()


class TestTestSuite(TestCaseWithFactory):
    """
    Test suite naming
    """

    def test_result_store(self):
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(), self.user)
        store = JobPipeline.get(job.id)
        self.assertIsNotNone(store)
        self.assertIsInstance(store, JobPipeline)
        self.assertIs(type(store.pipeline), dict)
        self.factory.cleanup()

    def test_pipelinestore(self):
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(), self.user)
        result_samples = [
            {"case": "test-runscript-overlay", "definition": "lava", "duration": 1.8733930587768555, "level": "1.3.3.4", "result": "pass"},
            {"case": "apply-overlay-guest", "definition": "lava", "duration": 46.395780086517334, "level": "1.4", "result": "pass"},
            {"case": "smoke-tests-basic", "definition": "lava", "uuid": "44148c2f-3c7d-4143-889e-dd4a77084e07", "result": "fail"},
            {"case": "linux-INLINE-lscpu", "definition": "smoke-tests-basic", "result": "pass"},
            {"case": "smoke-tests-basic", "definition": "lava", "duration": "2.61", "uuid": "44148c2f-3c7d-4143-889e-dd4a77084e07", "result": "pass"}
        ]
        for sample in result_samples:
            ret = map_scanned_results(results=sample, job=job, meta_filename=None)
            self.assertTrue(ret)
        self.assertEqual(4, TestCase.objects.count())
        val = URLValidator()
        for testcase in TestCase.objects.all():
            self.assertIsNotNone(testcase.name)
            self.assertIsNotNone(testcase.result)
            if testcase.test_set:
                val('http://localhost/%s' % testcase.get_absolute_url())
        self.factory.cleanup()

    def test_level_input(self):
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(), self.user)
        suite = TestSuite.objects.create(
            job=job,
            name='lava'
        )
        suite.save()
        ret = map_scanned_results(
            results={"case": "test-overlay", "definition": "lava",
                     "duration": 0.01159811019897461, "level": "1.3.3.2",
                     "result": "pass"}, job=job, meta_filename=None)
        self.assertTrue(ret)
        self.assertEqual(1, TestCase.objects.filter(suite=suite).count())
        testcase = TestCase.objects.get(suite=suite)
        self.assertTrue(type(testcase.metadata) in [str, unicode])
        self.assertEqual(testcase.result, TestCase.RESULT_PASS)
        self.factory.cleanup()

    def test_bad_input(self):
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(), self.user)
        # missing {'results'} key
        result_samples = [
            {"definition": "lava", "result": "pass"},
            {"case": "test-runscript-overlay", "result": "pass"},
            {"case": "test-runscript-overlay", "definition": "lava"},
            {}
        ]
        for sample in result_samples:
            ret = map_scanned_results(results=sample, job=job, meta_filename=None)
            self.assertFalse(ret)
        self.factory.cleanup()

    def test_set(self):
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(), self.user)
        result_samples = [
            {"case": "linux-INLINE-lscpu", "definition": "smoke-tests-basic", "result": "fail", "set": "listing"},
            {"case": "linux-INLINE-lspci", "definition": "smoke-tests-basic", "result": "fail", "set": "listing"}
        ]
        suite = TestSuite.objects.create(
            job=job,
            name='test-suite'
        )
        suite.save()
        self.assertEqual('/results/%s/test-suite' % job.id, suite.get_absolute_url())

        for sample in result_samples:
            ret = map_scanned_results(results=sample, job=job, meta_filename=None)
            self.assertTrue(ret)

        self.assertEqual(2, TestCase.objects.count())
        val = URLValidator()
        for testcase in TestCase.objects.filter(suite=suite):
            self.assertEqual(testcase.suite, suite)
            self.assertIsNotNone(testcase.name)
            self.assertIsNotNone(testcase.result)
            self.assertIsNone(testcase.metadata)
            self.assertEqual(testcase.result, TestCase.RESULT_PASS)
            self.assertEqual(testcase.test_set.name, 'listing')
            self.assertTrue(testcase.name.startswith('linux-INLINE-'))
            val('http://localhost/%s' % testcase.get_absolute_url())
        self.factory.cleanup()
