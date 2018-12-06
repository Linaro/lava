import os
import yaml
import logging
import unittest
from nose.tools import nottest
from io import BytesIO as StringIO
import xmlrpc.client
from django.test.client import Client
from django.contrib.auth.models import Permission
from lava_scheduler_app.dbutils import validate_yaml
from lava_scheduler_app.models import DeviceType, Alias
from lava_scheduler_app.schema import (
    validate_submission,
    validate_device,
    SubmissionException,
)
from lava_scheduler_app.tests.test_submission import TestCaseWithFactory

# pylint: disable=invalid-name


# Based on http://www.technobabble.dk/2008/apr/02/xml-rpc-dispatching-through-django-test-client/
@nottest
class TestTransport(xmlrpc.client.Transport, object):
    """Handles connections to XML-RPC server through Django test client."""

    def __init__(self, user=None, password=None):
        super().__init__()
        self.client = Client()
        if user:
            success = self.client.login(username=user, password=password)
            if not success:
                raise AssertionError("Login attempt failed!")
        self._use_datetime = True
        self.verbose = 0

    def request(self, host, handler, request_body, verbose=0):
        self.verbose = verbose
        response = self.client.post(handler, request_body, content_type="text/xml")
        res = StringIO(response.content)
        res.seek(0)
        return self.parse_response(res)


class TestSchedulerAPI(TestCaseWithFactory):  # pylint: disable=too-many-ancestors
    def setUp(self):
        super().setUp()
        logger = logging.getLogger("lava-master")
        logger.disabled = True
        logger = logging.getLogger("lava_scheduler_app")
        logger.disabled = True

    def server_proxy(self, user=None, password=None):  # pylint: disable=no-self-use
        return xmlrpc.client.ServerProxy(
            "http://localhost/RPC2/",
            transport=TestTransport(user=user, password=password),
        )

    def test_submit_job_rejects_anonymous(self):
        server = self.server_proxy()
        try:
            server.scheduler.submit_job("{}")
        except xmlrpc.client.Fault as f:
            self.assertEqual(401, f.faultCode)
        else:
            self.fail("fault not raised")

    def test_submit_job_rejects_unpriv_user(self):
        self.factory.ensure_user("unpriv-test", "e@mail.invalid", "test")
        server = self.server_proxy("unpriv-test", "test")
        try:
            server.scheduler.submit_job("{}")
        except xmlrpc.client.Fault as f:
            self.assertEqual(403, f.faultCode)
        else:
            self.fail("fault not raised")

    def test_new_devices(self):
        user = self.factory.ensure_user("test", "e@mail.invalid", "test")
        user.user_permissions.add(Permission.objects.get(codename="add_testjob"))
        user.save()
        device_type = self.factory.make_device_type("beaglebone-black")
        device = self.factory.make_device(device_type=device_type, hostname="black01")
        device.save()
        server = self.server_proxy("test", "test")
        self.assertEqual(
            {
                "status": "offline",
                "job": None,
                "offline_since": None,
                "hostname": "black01",
                "offline_by": None,
                "is_pipeline": True,
            },
            server.scheduler.get_device_status("black01"),
        )

    def test_type_aliases(self):
        aliases = DeviceType.objects.filter(aliases__name__contains="black")
        retval = {"black": [device_type.name for device_type in aliases]}
        self.assertEqual(retval, {"black": []})
        device_type = self.factory.make_device_type("beaglebone-black")
        alias = Alias.objects.create(name="am335x-boneblack")
        device_type.aliases.add(alias)
        aliases = DeviceType.objects.filter(aliases__name__contains="black")
        retval = {"black": [dt.name for dt in aliases]}
        self.assertEqual(retval, {"black": ["beaglebone-black"]})
        alias.delete()
        aliases = DeviceType.objects.filter(aliases__name__contains="black")
        retval = {"black": [dt.name for dt in aliases]}
        self.assertEqual(retval, {"black": []})


class TestVoluptuous(unittest.TestCase):
    def test_submission_schema(self):
        files = []
        path = os.path.normpath(os.path.dirname(__file__))
        for name in os.listdir(path):
            if name.endswith(".yaml"):
                files.append(name)
        device_files = [
            # device files supporting unit tests
            "bbb-01.yaml"
        ]
        # these files have already been split by utils as multinode sub_id jobs.
        # FIXME: validate the schema of split files using lava-dispatcher.
        split_files = [
            "kvm-multinode-client.yaml",
            "kvm-multinode-server.yaml",
            "qemu-ssh-guest-1.yaml",
            "qemu-ssh-guest-2.yaml",
            "qemu-ssh-parent.yaml",
        ]

        for filename in files:
            # some files are dispatcher-level test files, e.g. after the multinode split
            try:
                yaml_data = yaml.safe_load(open(os.path.join(path, filename), "r"))
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
                    msg = "########## %s ###########\n%s" % (filename, exc)
                    self.fail(msg)

    def test_breakage_detection(self):
        bad_submission = """
timeouts:
  job:
    minutes: 15
  action:
    minutes: 5
                """
        self.assertRaises(
            SubmissionException, validate_submission, yaml.safe_load(bad_submission)
        )
        try:
            validate_submission(yaml.safe_load(bad_submission))
        except SubmissionException as exc:
            # with more than one omission, which one gets mentioned is undefined
            self.assertIn("required key not provided", str(exc))
        bad_submission += """
actions:
  - deploy:
      to: tmpfs
                """
        self.assertRaises(
            SubmissionException, validate_submission, yaml.safe_load(bad_submission)
        )
        try:
            validate_submission(yaml.safe_load(bad_submission))
        except SubmissionException as exc:
            self.assertIn("required key not provided", str(exc))
            # with more than one omission, which one gets mentioned is undefined
            self.assertTrue("visibility" in str(exc) or "job_name" in str(exc))
        bad_submission += """
visibility: public
                """
        self.assertRaises(
            SubmissionException, validate_submission, yaml.safe_load(bad_submission)
        )
        try:
            validate_submission(yaml.safe_load(bad_submission))
        except SubmissionException as exc:
            self.assertIn("required key not provided", str(exc))
            self.assertIn("job_name", str(exc))
        bad_submission += """
job_name: qemu-pipeline
                """
        self.assertTrue(validate_submission(yaml.safe_load(bad_submission)))
        bad_yaml = yaml.safe_load(bad_submission)
        del bad_yaml["timeouts"]["job"]
        try:
            validate_submission(yaml.safe_load(bad_submission))
        except SubmissionException as exc:
            self.assertIn("required key not provided", str(exc))
            self.assertIn("job", str(exc))
            self.assertIn("timeouts", str(exc))
        bad_submission += """
notify:
  criteria:
    status: complete
        """
        self.assertTrue(validate_submission(yaml.safe_load(bad_submission)))
        bad_submission += """
  compare:
    query:
      entity: testrunfilter
        """
        self.assertRaises(
            SubmissionException, validate_yaml, yaml.safe_load(bad_submission)
        )

        invalid_monitors_name_char_yaml_def = r"""
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

        self.assertRaises(
            SubmissionException,
            validate_submission,
            yaml.safe_load(invalid_monitors_name_char_yaml_def),
        )

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
          compression: gz
        os: oe
        # breakage at the dtb block of a tftp deploy
        dtb:
          location: http://test.com/baz
                """
        try:
            validate_submission(yaml.safe_load(bad_submission))
        except SubmissionException as exc:
            self.assertIn("required key not provided", str(exc))
            self.assertIn("dtb", str(exc))
            self.assertIn("url", str(exc))

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
          compression: gz
        os: oe
        # breakage using the original syntax
        dtb: http://test.com/baz
                """
        try:
            validate_submission(yaml.safe_load(bad_submission))
        except SubmissionException as exc:
            self.assertIn("expected a dictionary for dictionary value", str(exc))
            self.assertIn("dtb", str(exc))
            self.assertNotIn("url", str(exc))

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
        self.assertTrue(validate_submission(yaml.safe_load(secrets)))
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
        self.assertRaises(
            SubmissionException, validate_submission, yaml.safe_load(secrets)
        )

    def test_multinode(self):
        # Without protocols
        data = """
job_name: test
visibility: public
timeouts:
  job:
    minutes: 10
  action:
    minutes: 5
actions: []
"""
        self.assertTrue(validate_submission(yaml.safe_load(data)))

        data = """
job_name: test
visibility: public
timeouts:
  job:
    minutes: 10
  action:
    minutes: 5
actions: []
protocols: {}
"""
        self.assertTrue(validate_submission(yaml.safe_load(data)))

        # With a valid multinode protocol
        data = """
job_name: test
visibility: public
timeouts:
  job:
    minutes: 10
  action:
    minutes: 5
actions: []
protocols:
  lava-multinode:
    roles:
      guest: {}
      host: {}
"""
        self.assertTrue(validate_submission(yaml.safe_load(data)))

        data = """
job_name: test
visibility: public
timeouts:
  job:
    minutes: 10
  action:
    minutes: 5
actions: []
protocols:
  lava-multinode:
    roles:
      guest:
        host_role: host
        expect_role: host
      host: {}
"""
        self.assertTrue(validate_submission(yaml.safe_load(data)))

        # invalid host_role or expect_role
        data = """
job_name: test
visibility: public
timeouts:
  job:
    minutes: 10
  action:
    minutes: 5
actions: []
protocols:
  lava-multinode:
    roles:
      guest:
        host_role: server
      host: {}
"""
        self.assertRaises(
            SubmissionException, validate_submission, yaml.safe_load(data)
        )

        data = """
job_name: test
visibility: public
timeouts:
  job:
    minutes: 10
  action:
    minutes: 5
actions: []
protocols:
  lava-multinode:
    roles:
      guest:
        host_role: host
        expect_role: server
      host: {}
"""
        self.assertRaises(
            SubmissionException, validate_submission, yaml.safe_load(data)
        )

        # host_role without expect_role
        data = """
job_name: test
visibility: public
timeouts:
  job:
    minutes: 10
  action:
    minutes: 5
actions: []
protocols:
  lava-multinode:
    roles:
      guest:
        host_role: host
      host: {}
"""
        self.assertRaises(
            SubmissionException, validate_submission, yaml.safe_load(data)
        )

        # expect_role without host_role
        data = """
job_name: test
visibility: public
timeouts:
  job:
    minutes: 10
  action:
    minutes: 5
actions: []
protocols:
  lava-multinode:
    roles:
      guest:
        expect_role: host
      host: {}
"""
        self.assertRaises(
            SubmissionException, validate_submission, yaml.safe_load(data)
        )
