import os
import sys
import yaml
import json
import logging
import cStringIO
import xmlrpclib
import unittest
from django.test import TransactionTestCase
from django.test.client import Client
from django.contrib.auth.models import Permission, User
from django.utils import timezone
from lava_scheduler_app.models import (
    Device,
    DeviceType,
    Tag,
    TestJob,
    TemporaryDevice,
    validate_yaml,
    Alias,
)
from lava_scheduler_daemon.dbjobsource import DatabaseJobSource
from lava_scheduler_app.schema import validate_submission, validate_device, SubmissionException
from lava_scheduler_app.dbutils import (
    testjob_submission, get_job_queue,
    find_device_for_job,
    get_available_devices,
)
from lava_scheduler_app.tests.test_submission import ModelFactory, TestCaseWithFactory
# pylint: disable=invalid-name


# Based on http://www.technobabble.dk/2008/apr/02/xml-rpc-dispatching-through-django-test-client/
class TestTransport(xmlrpclib.Transport, object):
    """Handles connections to XML-RPC server through Django test client."""

    def __init__(self, user=None, password=None):
        super(TestTransport, self).__init__()
        self.client = Client()
        if user:
            success = self.client.login(username=user, password=password)
            if not success:
                raise AssertionError("Login attempt failed!")
        self._use_datetime = True
        self.verbose = 0

    def request(self, host, handler, request_body, verbose=0):
        self.verbose = verbose
        response = self.client.post(
            handler, request_body, content_type="text/xml")
        res = cStringIO.StringIO(response.content)
        res.seek(0)
        return self.parse_response(res)


class TestSchedulerAPI(TestCaseWithFactory):  # pylint: disable=too-many-ancestors

    def setUp(self):
        super(TestSchedulerAPI, self).setUp()
        logger = logging.getLogger('dispatcher-master')
        logger.disabled = True
        logger = logging.getLogger('lava_scheduler_app')
        logger.disabled = True

    def server_proxy(self, user=None, password=None):  # pylint: disable=no-self-use
        return xmlrpclib.ServerProxy(
            'http://localhost/RPC2/',
            transport=TestTransport(user=user, password=password))

    def test_submit_job_rejects_anonymous(self):
        server = self.server_proxy()
        try:
            server.scheduler.submit_job("{}")
        except xmlrpclib.Fault as f:
            self.assertEqual(401, f.faultCode)
        else:
            self.fail("fault not raised")

    def test_submit_job_rejects_unpriv_user(self):
        self.factory.ensure_user('unpriv-test', 'e@mail.invalid', 'test')
        server = self.server_proxy('unpriv-test', 'test')
        try:
            server.scheduler.submit_job("{}")
        except xmlrpclib.Fault as f:
            self.assertEqual(403, f.faultCode)
        else:
            self.fail("fault not raised")

    def test_new_devices(self):
        user = self.factory.ensure_user('test', 'e@mail.invalid', 'test')
        user.user_permissions.add(
            Permission.objects.get(codename='add_testjob'))
        user.save()
        device_type = self.factory.make_device_type('beaglebone-black')
        device = self.factory.make_device(device_type=device_type, hostname="black01")
        device.save()
        server = self.server_proxy('test', 'test')
        self.assertEqual(
            {'status': 'idle', 'job': None, 'offline_since': None, 'hostname': 'black01',
                'offline_by': None, 'is_pipeline': False},
            server.scheduler.get_device_status('black01'))
        offline_device = self.factory.make_device(device_type=device_type, hostname="black02", status=Device.OFFLINE)
        offline_device.save()
        self.assertEqual(
            {'status': 'offline', 'job': None, 'offline_since': '', 'hostname': 'black02',
                'offline_by': '', 'is_pipeline': False},
            server.scheduler.get_device_status('black02')
        )

    def test_type_aliases(self):
        aliases = DeviceType.objects.filter(aliases__name__contains='black')
        retval = {
            'black': [device_type.name for device_type in aliases]
        }
        self.assertEqual(retval, {'black': []})
        device_type = self.factory.make_device_type('beaglebone-black')
        alias = Alias.objects.create(name='am335x-boneblack')
        device_type.aliases.add(alias)
        aliases = DeviceType.objects.filter(aliases__name__contains='black')
        retval = {
            'black': [dt.name for dt in aliases]
        }
        self.assertEqual(retval, {'black': ['beaglebone-black']})
        alias.delete()
        aliases = DeviceType.objects.filter(aliases__name__contains='black')
        retval = {
            'black': [dt.name for dt in aliases]
        }
        self.assertEqual(retval, {'black': []})

    # comment out the decorator to run this queue timing test
    @unittest.skip('Developer only - timing test')
    def test_queueing(self):
        """
        uses stderr to avoid buffered prints
        Expect the test itself to take <30s and
        the gap between jobs submitted and end being ~500ms
        Most of the time is spent setting up the database
        and submitting all the test jobs.
        """
        sys.stderr.write(timezone.now(), "start")
        user = self.factory.ensure_user('test', 'e@mail.invalid', 'test')
        user.user_permissions.add(
            Permission.objects.get(codename='add_testjob'))
        user.save()
        device_type = self.factory.make_device_type('beaglebone-black')
        device = self.factory.make_device(device_type=device_type, hostname="black01")
        device.save()
        device_type = self.factory.make_device_type('wandboard')
        count = 1
        while count < 100:
            suffix = "{:02d}".format(count)
            device = self.factory.make_device(device_type=device_type, hostname="imx6q-%s" % suffix)
            device.save()
            count += 1
        sys.stderr.write(timezone.now(), "%d dummy devices created" % count)
        device_list = list(get_available_devices())
        sys.stderr.write(timezone.now(), "%d available devices" % len(device_list))
        filename = os.path.join(os.path.dirname(__file__), 'sample_jobs', 'master-check.json')
        self.assertTrue(os.path.exists(filename))
        with open(filename, 'r') as json_file:
            definition = json_file.read()
        count = 0
        # each 1000 more can take ~15s in the test.
        while count < 1000:
            # simulate API submission
            job = testjob_submission(definition, user)
            self.assertFalse(job.health_check)
            count += 1
        sys.stderr.write(timezone.now(), "%d jobs submitted" % count)
        jobs = list(get_job_queue())
        self.assertIsNotNone(jobs)
        sys.stderr.write(timezone.now(), "Finding devices for jobs.")
        for job in jobs:
            # this needs to stay as a tight loop to cope with load
            device = find_device_for_job(job, device_list)
            if device:
                sys.stderr.write(timezone.now(), "[%d] allocated %s" % (job.id, device))
                device_list.remove(device)
        sys.stderr.write(timezone.now(), "end")


class TransactionTestCaseWithFactory(TransactionTestCase):

    def setUp(self):
        TransactionTestCase.setUp(self)
        self.factory = ModelFactory()


class NonthreadedDatabaseJobSource(DatabaseJobSource):
    deferToThread = staticmethod(lambda f, *args, **kw: f(*args, **kw))


class TestDBJobSource(TransactionTestCaseWithFactory):

    def setUp(self):
        super(TestDBJobSource, self).setUp()
        self.source = NonthreadedDatabaseJobSource()
        # The lava-health user is created by a migration in production
        # databases, but removed from the test database by the django
        # machinery.
        User.objects.create_user(
            username='lava-health', email='lava@lava.invalid')

    @property
    def health_job(self):
        return self.factory.make_job_json(health_check=True)

    @property
    def ordinary_job(self):
        return self.factory.make_job_json(health_check=False)

    def assertHealthJobAssigned(self, device):
        pass

    def assertHealthJobNotAssigned(self, device):
        pass

    def _makeBoardWithTags(self, tags):
        board = self.factory.make_device()
        for tag_name in tags:
            board.tags.add(Tag.objects.get_or_create(name=tag_name)[0])
        return board

    def _makeJobWithTagsForBoard(self, tags, board):
        job = self.factory.make_testjob(requested_device=board)
        for tag_name in tags:
            job.tags.add(Tag.objects.get_or_create(name=tag_name)[0])
        return job

    def assertBoardWithTagsGetsJobWithTags(self, board_tags, job_tags):
        pass

    def assertBoardWithTagsDoesNotGetJobWithTags(self, board_tags, job_tags):
        pass


class TestVoluptuous(unittest.TestCase):

    def test_submission_schema(self):
        files = []
        path = os.path.normpath(os.path.dirname(__file__))
        for name in os.listdir(path):
            if name.endswith('.yaml'):
                files.append(name)
        device_files = [
            # device files supporting unit tests
            'bbb-01.yaml'
        ]
        # these files have already been split by utils as multinode sub_id jobs.
        # FIXME: validate the schema of split files using lava-dispatcher.
        split_files = [
            'kvm-multinode-client.yaml',
            'kvm-multinode-server.yaml',
            'qemu-ssh-guest-1.yaml',
            'qemu-ssh-guest-2.yaml',
            'qemu-ssh-parent.yaml'
        ]

        for filename in files:
            # some files are dispatcher-level test files, e.g. after the multinode split
            try:
                yaml_data = yaml.load(open(os.path.join(path, filename), 'r'))
            except yaml.YAMLError as exc:
                raise RuntimeError("Decoding YAML job submission failed: %s." % exc)
            if filename in device_files:
                validate_device(yaml_data)
                continue
            if filename in split_files:
                self.assertRaises(SubmissionException, validate_submission, yaml_data)
            else:
                try:
                    ret = validate_submission(yaml_data)
                    self.assertTrue(ret)
                except SubmissionException as exc:
                    msg = '########## %s ###########\n%s' % (filename, exc)
                    self.fail(msg)

    def test_breakage_detection(self):
        bad_submission = """
timeouts:
  job:
    minutes: 15
  action:
    minutes: 5
                """
        self.assertRaises(SubmissionException, validate_submission, yaml.load(bad_submission))
        try:
            validate_submission(yaml.load(bad_submission))
        except SubmissionException as exc:
            # with more than one omission, which one gets mentioned is undefined
            self.assertIn('required key not provided', str(exc))
        bad_submission += """
actions:
  - deploy:
      to: tmpfs
                """
        self.assertRaises(SubmissionException, validate_submission, yaml.load(bad_submission))
        try:
            validate_submission(yaml.load(bad_submission))
        except SubmissionException as exc:
            self.assertIn('required key not provided', str(exc))
            # with more than one omission, which one gets mentioned is undefined
            self.assertTrue('visibility' in str(exc) or 'job_name' in str(exc))
        bad_submission += """
visibility: public
                """
        self.assertRaises(SubmissionException, validate_submission, yaml.load(bad_submission))
        try:
            validate_submission(yaml.load(bad_submission))
        except SubmissionException as exc:
            self.assertIn('required key not provided', str(exc))
            self.assertIn('job_name', str(exc))
        bad_submission += """
job_name: qemu-pipeline
                """
        self.assertTrue(validate_submission(yaml.load(bad_submission)))
        bad_yaml = yaml.load(bad_submission)
        del bad_yaml['timeouts']['job']
        try:
            validate_submission(yaml.load(bad_submission))
        except SubmissionException as exc:
            self.assertIn('required key not provided', str(exc))
            self.assertIn('job', str(exc))
            self.assertIn('timeouts', str(exc))
        bad_submission += """
notify:
  criteria:
    status: complete
        """
        self.assertTrue(validate_submission(yaml.load(bad_submission)))
        bad_submission += """
  compare:
    query:
      entity: testrunfilter
        """
        self.assertRaises(SubmissionException, validate_yaml,
                          yaml.load(bad_submission))

        invalid_monitors_name_char_yaml_def = """
# Zephyr JOB definition
device_type: 'arduino101'
job_name: 'zephyr-upstream master drivers/spi/spi_basic_api/test_spi'
timeouts:
  job:
    minutes: 6
  action:
    minutes: 2
  actions:
    wait-usb-device:
      seconds: 40
priority: medium
visibility: public
actions:
- deploy:
    timeout:
      minutes: 3
    to: tmpfs
    type: monitor
    images:
        app:
          image_arg: --alt x86_app --download {app}
          url: 'https://snapshots.linaro.org/components/kernel/zephyr/master/zephyr/arduino_101/722/tests/drivers/spi/spi_basic_api/test_spi/zephyr.bin'
- boot:
    method: dfu
    timeout:
      minutes: 10
- test:
    monitors:
    - name: drivers/spi/spi_basic_api/test_spi
      start: tc_start()
      end: PROJECT EXECUTION
      pattern: (?P<result>(PASS|FAIL))\s-\s(?P<test_case_id>\w+)\.
      fixupdict:
        PASS: pass
        FAIL: fail
"""

        self.assertRaises(SubmissionException, validate_submission,
                          yaml.load(invalid_monitors_name_char_yaml_def))

    def test_compression_change(self):

        bad_submission = """
job_name: bbb-ramdisk
visibility: public
timeouts:
  job:
    minutes: 15
  action:
    minutes: 5
actions:
    - deploy:
        to: tftp
        kernel:
          url: http://test.com/foo
        ramdisk:
          url: http://test.com/bar
          header: u-boot
          add-header: u-boot
          compression: gz
        os: oe
        # breakage at the dtb block of a tftp deploy
        dtb:
          location: http://test.com/baz
                """
        try:
            validate_submission(yaml.load(bad_submission))
        except SubmissionException as exc:
            self.assertIn('required key not provided', str(exc))
            self.assertIn('dtb', str(exc))
            self.assertIn('url', str(exc))

        bad_submission = """
job_name: bbb-ramdisk
visibility: public
timeouts:
  job:
    minutes: 15
  action:
    minutes: 5
actions:
    - deploy:
        to: tftp
        kernel:
          url: http://test.com/foo
        ramdisk:
          url: http://test.com/bar
          header: u-boot
          add-header: u-boot
          compression: gz
        os: oe
        # breakage using the original syntax
        dtb: http://test.com/baz
                """
        try:
            validate_submission(yaml.load(bad_submission))
        except SubmissionException as exc:
            self.assertIn('expected a dictionary for dictionary value', str(exc))
            self.assertIn('dtb', str(exc))
            self.assertNotIn('url', str(exc))

    def test_secrets(self):
        secrets = """
job_name: kvm-test
visibility: personal
timeouts:
  job:
    minutes: 10
  action:
    minutes: 5
actions:
- deploy:
    to: tmpfs
    images:
      rootfs:
        url: //images.validation.linaro.org/kvm-debian-wheezy.img.gz
        compression: gz
    os: debian
secrets:
  foo: bar
  username: secret
"""
        self.assertTrue(validate_submission(yaml.load(secrets)))
        secrets = """
job_name: kvm-test
visibility: public
timeouts:
  job:
    minutes: 10
  action:
    minutes: 5
actions:
- deploy:
    to: tmpfs
    images:
      rootfs:
        url: //images.validation.linaro.org/kvm-debian-wheezy.img.gz
        compression: gz
    os: debian
secrets:
  foo: bar
  username: secret
"""
        self.assertRaises(SubmissionException, validate_submission, yaml.load(secrets))
