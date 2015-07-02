import os
import yaml
import logging
from collections import OrderedDict
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

    def cleanup(self):
        DeviceType.objects.all().delete()
        # make sure the DB is in a clean state wrt devices and jobs
        Device.objects.all().delete()
        TestJob.objects.all().delete()
        [item.delete() for item in DeviceDictionary.object_list()]

    def make_user(self):
        return User.objects.create_user(
            self.getUniqueString(),
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
        qemu.parameters = {'extends': 'qemu.yaml', 'arch': 'amd64'}
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


class TestTestSuite(TestCaseWithFactory):
    """
    Test suite naming
    """

    def test_result_store(self):
        user = self.factory.make_user()
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(), user)
        store = JobPipeline.get(job.id)
        self.assertIsNotNone(store)
        self.assertIsInstance(store, JobPipeline)
        self.assertIs(type(store.pipeline), dict)
        self.factory.cleanup()

    def test_name(self):
        user = self.factory.make_user()
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(), user)
        result_sample = """
- results: !!python/object/apply:collections.OrderedDict
  - - [linux-linaro-ubuntu-pwd, pass]
    - [linux-linaro-ubuntu-uname, pass]
    - [linux-linaro-ubuntu-vmstat, pass]
    - [linux-linaro-ubuntu-ifconfig, pass]
    - [linux-linaro-ubuntu-lscpu, pass]
    - [linux-linaro-ubuntu-lsb_release, pass]
    - [linux-linaro-ubuntu-netstat, pass]
    - [linux-linaro-ubuntu-ifconfig-dump, pass]
    - [linux-linaro-ubuntu-route-dump-a, pass]
    - [linux-linaro-ubuntu-route-ifconfig-up-lo, pass]
    - [linux-linaro-ubuntu-route-dump-b, pass]
    - [linux-linaro-ubuntu-route-ifconfig-up, pass]
    - [ping-test, fail]
    - [realpath-check, fail]
    - [ntpdate-check, pass]
    - [curl-ftp, pass]
    - [tar-tgz, pass]
    - [remove-tgz, pass]
        """
        scanned = yaml.load(result_sample)[0]
        suite = TestSuite.objects.create(
            job=job,
            name='test-suite'
        )
        suite.save()
        for testcase, result in scanned['results'].items():
            TestCase.objects.create(
                name=testcase,
                suite=suite,
                result=TestCase.RESULT_MAP[result]
            ).save()
        self.assertIsNot([], TestCase.objects.all())
        for testcase in TestCase.objects.all():
            self.assertEqual(testcase.suite, suite)
            self.assertIsNotNone(testcase.name)
            self.assertIsNotNone(testcase.result)
        self.factory.cleanup()

    def test_pipelinestore(self):
        user = self.factory.make_user()
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(), user)
        result_sample = {
            'results': {
                'test-runscript-overlay': OrderedDict([
                    ('success', 'c66c77b2-bc32-4cec-bc6d-477712da7eb6'),
                    ('filename', '/tmp/tmp9ICoFn/lava-device/tests/2_singlenode-advanced/run.sh')]),
                'test-install-overlay': OrderedDict([
                    ('success', 'c66c77b2-bc32-4cec-bc6d-477712da7eb6')]),
                'power_off': OrderedDict([('status', 'Complete')]),
                'test-overlay': OrderedDict([('success', 'c66c77b2-bc32-4cec-bc6d-477712da7eb6')]),
                'git-repo-action': OrderedDict([('success', '6dd3121dc7f2855d710e83fe39c217392e4fb2b4')]),
                'lava-test-shell': OrderedDict([
                    ('linux-linaro-ubuntu-pwd', 'pass'),
                    ('linux-linaro-ubuntu-uname', 'pass'),
                    ('linux-linaro-ubuntu-vmstat', 'pass'),
                    ('linux-linaro-ubuntu-ifconfig', 'pass'),
                    ('linux-linaro-ubuntu-lscpu', 'pass'),
                    ('linux-linaro-ubuntu-lsb_release', 'fail'),
                    ('linux-linaro-ubuntu-netstat', 'pass'),
                    ('linux-linaro-ubuntu-ifconfig-dump', 'pass'),
                    ('linux-linaro-ubuntu-route-dump-a', 'pass'),
                    ('linux-linaro-ubuntu-route-ifconfig-up-lo', 'pass'),
                    ('linux-linaro-ubuntu-route-dump-b', 'pass'),
                    ('linux-linaro-ubuntu-route-ifconfig-up', 'pass'),
                    ('ping-test', 'fail'),
                    ('realpath-check', 'fail'),
                    ('ntpdate-check', 'pass'),
                    ('curl-ftp', 'pass'),
                    ('tar-tgz', 'pass'),
                    ('remove-tgz', 'pass')])}
        }
        ret = map_scanned_results(scanned_dict=result_sample, job=job)
        self.assertTrue(ret)
        self.assertIsNot([], TestCase.objects.all())
        self.assertIsNot([], TestCase.objects.all())
        val = URLValidator()
        for testcase in TestCase.objects.all():
            self.assertIsNotNone(testcase.name)
            self.assertIsNotNone(testcase.result)
            if testcase.test_set:
                val('http://localhost/%s' % testcase.get_absolute_url())
        self.assertIsNotNone(TestCase.objects.filter(name='ping-test'))
        self.factory.cleanup()

    def test_level_input(self):
        user = self.factory.make_user()
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(), user)
        suite = TestSuite.objects.create(
            job=job,
            name='test-suite'
        )
        suite.save()
        result_sample = """
results:
  lava-test-shell: !!python/object/apply:collections.OrderedDict
    - - [ping-test, fail]
  power_off: !!python/object/apply:collections.OrderedDict
    - - [status, Complete]
      - [level, 5.1]
        """
        scanned = yaml.load(result_sample)
        ret = map_scanned_results(scanned_dict=scanned, job=job)
        self.assertTrue(ret)
        for testcase in TestCase.objects.filter(suite=suite):
            if testcase.name == 'power_off':
                self.assertTrue(type(testcase.metadata) in [str, unicode])
                self.assertTrue(type(testcase.action_data) == OrderedDict)
                self.assertEqual(testcase.action_data['status'], 'Complete')
                self.assertEqual(testcase.action_data['level'], 5.1)
                self.assertEqual(testcase.action_level, '5.1')
                self.assertEqual(testcase.result, TestCase.RESULT_UNKNOWN)
        self.factory.cleanup()

    def test_bad_input(self):
        user = self.factory.make_user()
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(), user)
        # missing {'results'} key
        result_sample = """
lava-test-shell: !!python/object/apply:collections.OrderedDict
  - - [ping-test, fail]
    - [realpath-check, fail]
    - [ntpdate-check, pass]
    - [curl-ftp, pass]
    - [tar-tgz, pass]
    - [remove-tgz, pass]
        """
        scanned = yaml.load(result_sample)
        suite = TestSuite.objects.create(
            job=job,
            name='test-suite'
        )
        suite.save()
        self.assertEqual('/results/%s/test-suite' % job.id, suite.get_absolute_url())
        ret = map_scanned_results(scanned_dict=scanned, job=job)
        self.assertFalse(ret)

        result_sample = """
results:
  lava-test-shell: !!python/object/apply:collections.OrderedDict
    - - [ping-test, fail]
  power_off: !!python/object/apply:collections.OrderedDict
    - - [status, Complete]
        """
        scanned = yaml.load(result_sample)
        self.assertEqual('/results/%s/test-suite' % job.id, suite.get_absolute_url())
        ret = map_scanned_results(scanned_dict=scanned, job=job)
        self.assertTrue(ret)
        for testcase in TestCase.objects.filter(suite=suite):
            if testcase.name == 'power_off':
                self.assertTrue(type(testcase.metadata) in [str, unicode])
                self.assertTrue(type(testcase.action_data) == OrderedDict)
                self.assertEqual(testcase.action_data['status'], 'Complete')
                self.assertEqual(testcase.result, TestCase.RESULT_UNKNOWN)
            elif testcase.name == 'ping-test':
                self.assertIsNone(testcase.metadata)
                self.assertEqual(testcase.result, TestCase.RESULT_FAIL)
            else:
                self.fail("Unrecognised testcase name")
        self.factory.cleanup()

    def test_set(self):
        user = self.factory.make_user()
        job = TestJob.from_yaml_and_user(
            self.factory.make_job_yaml(), user)
        result_sample = """
results:
    lava-test-shell: !!python/object/apply:collections.OrderedDict
      - - [ping-test, fail]
        - - set-name
          - !!python/object/apply:collections.OrderedDict
            - - [linux-linaro-foo, pass]
              - [linux-linaro-ubuntu-uname, pass]
              - [linux-linaro-ubuntu-vmstat, pass]
              - [linux-linaro-ubuntu-ifconfig, pass]
              - [linux-linaro-ubuntu-lscpu, pass]
              - [linux-linaro-ubuntu-lsb_release, pass]
              - [linux-linaro-ubuntu-netstat, pass]
              - [linux-linaro-ubuntu-ifconfig-dump, pass]
              - [linux-linaro-ubuntu-route-dump-a, pass]
              - [linux-linaro-ubuntu-route-ifconfig-up-lo, pass]
              - [linux-linaro-ubuntu-route-dump-b, pass]
              - [linux-linaro-ubuntu-route-ifconfig-up, pass]
        - [realpath-check, fail]
        - [ntpdate-check, pass]
        - [curl-ftp, pass]
        - [tar-tgz, pass]
        - [remove-tgz, pass]
        """
        scanned = yaml.load(result_sample)
        suite = TestSuite.objects.create(
            job=job,
            name='test-suite'
        )
        suite.save()
        self.assertEqual('/results/%s/test-suite' % job.id, suite.get_absolute_url())
        ret = map_scanned_results(scanned_dict=scanned, job=job)
        self.assertTrue(ret)
        self.assertIsNot([], TestCase.objects.all())
        val = URLValidator()
        for testcase in TestCase.objects.filter(suite=suite):
            self.assertEqual(testcase.suite, suite)
            self.assertIsNotNone(testcase.name)
            self.assertIsNotNone(testcase.result)
            self.assertIsNone(testcase.metadata)
            self.assertNotEqual(testcase.result, TestCase.RESULT_UNKNOWN)
            if testcase.test_set:
                self.assertEqual(testcase.test_set.name, 'set-name')
                self.assertTrue(testcase.name.startswith('linux-linaro'))
                val('http://localhost/%s' % testcase.get_absolute_url())
        self.factory.cleanup()
