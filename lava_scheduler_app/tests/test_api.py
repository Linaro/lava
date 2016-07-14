import os
import sys
import yaml
import json
import cStringIO
import xmlrpclib
import unittest
from django.test import TransactionTestCase
from django.test.client import Client
from django.contrib.auth.models import Permission, User
from django.utils import timezone
from lava_scheduler_app.models import (
    Device,
    DeviceStateTransition,
    Tag,
    TestJob,
    TemporaryDevice,
    validate_yaml,
)
from lava_scheduler_daemon.dbjobsource import DatabaseJobSource
from lava_scheduler_app.schema import validate_submission, validate_device, SubmissionException
from lava_scheduler_app.dbutils import(
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

    def test_submit_job_sets_definition(self):
        user = self.factory.ensure_user('test', 'e@mail.invalid', 'test')
        user.user_permissions.add(
            Permission.objects.get(codename='add_testjob'))
        user.save()
        server = self.server_proxy('test', 'test')
        definition = self.factory.make_job_json()
        job_id = server.scheduler.submit_job(definition)
        job = TestJob.objects.get(id=job_id)
        self.assertEqual(definition, job.definition)

    def test_cancel_job_rejects_anonymous(self):
        job = self.factory.make_testjob()
        server = self.server_proxy()
        try:
            server.scheduler.cancel_job(job.id)
        except xmlrpclib.Fault as f:
            self.assertEqual(401, f.faultCode)
        else:
            self.fail("fault not raised")

    def test_cancel_job_rejects_unpriv_user(self):
        job = self.factory.make_testjob()
        self.factory.ensure_user('test', 'e@mail.invalid', 'test')
        server = self.server_proxy('test', 'test')
        try:
            server.scheduler.cancel_job(job.id)
        except xmlrpclib.Fault as f:
            self.assertEqual(403, f.faultCode)
        else:
            self.fail("fault not raised")

    def test_cancel_job_cancels_job(self):
        user = self.factory.ensure_user('test', 'e@mail.invalid', 'test')
        job = self.factory.make_testjob(submitter=user)
        server = self.server_proxy('test', 'test')
        server.scheduler.cancel_job(job.id)
        job = TestJob.objects.get(pk=job.pk)
        self.assertIn(TestJob.STATUS_CHOICES[job.status], [
            TestJob.STATUS_CHOICES[TestJob.CANCELED],
            TestJob.STATUS_CHOICES[TestJob.CANCELING]
        ])

    def test_cancel_job_user(self):
        """
        tests whether the user who canceled the job is reflected properly.

        See: https://bugs.linaro.org/show_bug.cgi?id=650
        """
        user = self.factory.ensure_user('test', 'e@mail.invalid', 'test')
        cancel_user = User.objects.create_user('test_cancel',
                                               'cancel@mail.invalid',
                                               'test_cancel')
        cancel_user.save()
        job = self.factory.make_testjob(submitter=user)
        job.description = "sample job"
        job.save()
        job.cancel(user=cancel_user)
        job = TestJob.objects.get(pk=job.pk)
        self.assertIn(TestJob.STATUS_CHOICES[job.status], [
            TestJob.STATUS_CHOICES[TestJob.CANCELED],
            TestJob.STATUS_CHOICES[TestJob.CANCELING]
        ])
        job = TestJob.objects.get(pk=job.pk)  # reload
        self.assertEqual(job.failure_comment,
                         "Canceled by %s" % cancel_user.username)

    def test_json_vs_yaml(self):
        """
        Test that invalid JSON gets rejected but valid YAML is accepted as pipeline
        """
        user = self.factory.ensure_user('test', 'e@mail.invalid', 'test')
        user.user_permissions.add(
            Permission.objects.get(codename='add_testjob'))
        user.save()
        job = self.factory.make_testjob(submitter=user)
        self.assertFalse(job.is_pipeline)
        # "break" the JSON by dropping the closing } as JSON needs the complete file to validate
        invalid_def = job.definition[:-2]
        self.assertRaises(ValueError, json.loads, invalid_def)
        server = self.server_proxy('test', 'test')
        self.assertRaises(xmlrpclib.Fault, server.scheduler.submit_job, invalid_def)

        invalid_yaml_def = """
# Sample JOB definition for a KVM
device_type: qemu
job_name: kvm-pipeline
priority: medium
"""
        self.assertRaises(ValueError, json.loads, invalid_yaml_def)
        self.assertRaises(xmlrpclib.Fault, server.scheduler.submit_job, invalid_yaml_def)

        yaml_def = """
# Sample JOB definition for a KVM
device_type: qemu
job_name: kvm-pipeline
timeouts:
  job:
    minutes: 15
  action:
    minutes: 5
priority: medium
visibility: public
actions:

    - deploy:
        to: tmpfs
        image: http://images.validation.linaro.org/kvm-debian-wheezy.img.gz
        compression: gz
        os: debian

    - boot:
        method: qemu
        media: tmpfs
        failure_retry: 2

    - test:
        name: kvm-basic-singlenode
        definitions:
            - repository: git://git.linaro.org/qa/test-definitions.git
              from: git
              path: ubuntu/smoke-tests-basic.yaml
              # name: if not present, use the name from the YAML. The name can
              # also be overriden from the actual commands being run by
              # calling the lava-test-suite-name API call (e.g.
              # `lava-test-suite-name FOO`).
              name: smoke-tests
"""
        yaml_data = yaml.load(yaml_def)
        validate_submission(yaml_data)
        self.assertRaises(xmlrpclib.Fault, server.scheduler.submit_job, yaml_def)

        device_type = self.factory.make_device_type('qemu')
        device = self.factory.make_device(device_type=device_type, hostname="qemu1")
        device.save()
        self.assertFalse(device.is_pipeline)
        self.assertRaises(xmlrpclib.Fault, server.scheduler.submit_job, yaml_def)
        device = self.factory.make_device(device_type=device_type, hostname="qemu2", is_pipeline=True)
        device.save()
        self.assertTrue(device.is_pipeline)
        job_id = server.scheduler.submit_job(yaml_def)
        job = TestJob.objects.get(id=job_id)
        self.assertTrue(job.is_pipeline)

    def test_health_determination(self):  # pylint: disable=too-many-statements
        user = self.factory.ensure_user('test', 'e@mail.invalid', 'test')
        user.user_permissions.add(
            Permission.objects.get(codename='add_testjob'))
        user.save()
        device_type = self.factory.make_device_type('beaglebone-black')
        device = self.factory.make_device(device_type=device_type, hostname="black01")
        device.save()
        filename = os.path.join(os.path.dirname(__file__), 'master-check.json')
        self.assertTrue(os.path.exists(filename))
        with open(filename, 'r') as json_file:
            definition = json_file.read()
        # simulate UI submission
        job = self.factory.make_testjob(definition=definition, submitter=user)
        self.assertFalse(job.health_check)
        job.save(update_fields=['health_check', 'requested_device'])
        self.assertFalse(job.health_check)
        job.delete()
        # simulate API submission
        job = testjob_submission(definition, user)
        self.assertFalse(job.health_check)
        self.assertIsNone(job.requested_device)
        job.delete()
        job = testjob_submission(definition, user, check_device=None)
        self.assertFalse(job.health_check)
        self.assertIsNone(job.requested_device)
        job.delete()
        # simulate initiating a health check
        job = testjob_submission(definition, user, check_device=device)
        self.assertTrue(job.health_check)
        self.assertEqual(job.requested_device.hostname, device.hostname)
        job.delete()
        # modify definition to use the deprecated target support
        device2 = self.factory.make_device(device_type=device_type, hostname="black02")
        device2.save()
        def_dict = json.loads(definition)
        self.assertNotIn('target', def_dict)
        def_dict['target'] = device2.hostname
        definition = json.dumps(def_dict)
        # simulate API submission with target set
        job = testjob_submission(definition, user, check_device=None)
        self.assertFalse(job.health_check)
        self.assertEqual(job.requested_device.hostname, device2.hostname)
        job.delete()
        # healthcheck designation overrides target (although this is itself an admin error)
        job = testjob_submission(definition, user, check_device=device)
        self.assertTrue(job.health_check)
        self.assertEqual(job.requested_device.hostname, device.hostname)
        job.delete()
        # check malformed JSON
        self.assertRaises(SubmissionException, testjob_submission, definition[:100], user)
        # check non-existent targets
        def_dict['target'] = 'nosuchdevice'
        definition = json.dumps(def_dict)
        self.assertRaises(Device.DoesNotExist, testjob_submission, definition, user)
        # check multinode API submission. bug #2130
        filename = os.path.join(os.path.dirname(__file__), 'master-multinode.json')
        self.assertTrue(os.path.exists(filename))
        with open(filename, 'r') as json_file:
            definition = json_file.read()
        job_list = testjob_submission(definition, user)
        self.assertIsInstance(job_list, list)
        for job in job_list:
            self.assertIsNotNone(job.vm_group)
            self.assertFalse(job.health_check)
            if job.requested_device_type == device_type:
                self.assertIsNone(job.requested_device)
            else:
                self.assertIsNotNone(job.requested_device)
                self.assertIsInstance(job.requested_device, TemporaryDevice)
                job.requested_device.delete()
            job.delete()

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
            {'status': 'idle', 'job': None, 'offline_since': None, 'hostname': 'black01', 'offline_by': None},
            server.scheduler.get_device_status('black01'))
        offline_device = self.factory.make_device(device_type=device_type, hostname="black02", status=Device.OFFLINE)
        offline_device.save()
        self.assertEqual(
            {'status': 'offline', 'job': None, 'offline_since': '', 'hostname': 'black02', 'offline_by': ''},
            server.scheduler.get_device_status('black02')
        )

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
        print >> sys.stderr, timezone.now(), "start"
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
        print >> sys.stderr, timezone.now(), "%d dummy devices created" % count
        device_list = list(get_available_devices())
        print >> sys.stderr, timezone.now(), "%d available devices" % len(device_list)
        filename = os.path.join(os.path.dirname(__file__), 'master-check.json')
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
        print >> sys.stderr, timezone.now(), "%d jobs submitted" % count
        jobs = list(get_job_queue())
        self.assertIsNotNone(jobs)
        print >> sys.stderr, timezone.now(), "Finding devices for jobs."
        for job in jobs:
            # this needs to stay as a tight loop to cope with load
            device = find_device_for_job(job, device_list)
            if device:
                print >> sys.stderr, timezone.now(), "[%d] allocated %s" % (job.id, device)
                device_list.remove(device)
        print >> sys.stderr, timezone.now(), "end"


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
