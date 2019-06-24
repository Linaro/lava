import os
import pathlib
import pytest
import yaml
import logging
import unittest
from nose.tools import nottest
from io import BytesIO as StringIO
import xmlrpc.client

from django.contrib.auth.models import Group, Permission, User
from django.test.client import Client

from lava_scheduler_app.dbutils import validate_yaml
from lava_scheduler_app.models import Alias, Device, DeviceType, Tag, Worker
from lava_scheduler_app.schema import (
    validate_submission,
    validate_device,
    SubmissionException,
)
from lava_scheduler_app.tests.test_submission import TestCaseWithFactory

# pylint: disable=invalid-name


# Based on http://www.technobabble.dk/2008/apr/02/xml-rpc-dispatching-through-django-test-client/
@nottest
class TestTransport(xmlrpc.client.Transport):
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
        path = os.path.join(os.path.normpath(os.path.dirname(__file__)), "sample_jobs")
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


@pytest.fixture
def setup(db):
    user = User.objects.create_user(username="user", password="user")
    group = Group.objects.create(name="group")
    admin = User.objects.create_user(username="admin", password="admin")
    admin.user_permissions.add(Permission.objects.get(codename="add_device"))
    admin.user_permissions.add(Permission.objects.get(codename="add_tag"))
    admin.user_permissions.add(Permission.objects.get(codename="delete_tag"))
    admin.user_permissions.add(Permission.objects.get(codename="add_worker"))
    admin.user_permissions.add(Permission.objects.get(codename="change_worker"))


def server(user=None, password=None):
    return xmlrpc.client.ServerProxy(
        "http://localhost/RPC2/",
        transport=TestTransport(user=user, password=password),
        allow_none=True,
    )


@pytest.mark.django_db
def test_devices_add(setup):
    # 1. missing device-type and worker
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.devices.add("black01", "black", "worker01")
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "DeviceType 'black' was not found."

    # Create the device-type
    DeviceType.objects.create(name="black")
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.devices.add("black01", "black", "worker01")
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Worker 'worker01' was not found."

    Worker.objects.create(hostname="worker01")
    server("admin", "admin").scheduler.devices.add("black01", "black", "worker01")
    Device.objects.count() == 1
    Device.objects.all()[0].hostname == "black01"
    Device.objects.all()[0].device_type.name == "black"
    Device.objects.all()[0].worker_host.hostname == "worker01"
    Device.objects.all()[0].get_health_display() == "Unknown"

    # 2. test description, user, health, group
    server("admin", "admin").scheduler.devices.add(
        "black02",
        "black",
        "worker01",
        "user",
        "group",
        True,
        "MAINTENANCE",
        "second device",
    )

    Device.objects.count() == 2
    Device.objects.all()[1].hostname == "black02"
    Device.objects.all()[1].device_type.name == "black"
    Device.objects.all()[1].worker_host.hostname == "worker01"
    Device.objects.all()[1].user.username == "user"
    Device.objects.all()[1].group.name == "group"
    Device.objects.all()[1].get_health_display() == "Maintenance"

    # 3. wrong user, group or health
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.devices.add(
            "black03", "black", "worker01", "nope", "wrong"
        )
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "User 'nope' was not found."

    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.devices.add(
            "black03", "black", "worker01", None, "wrong"
        )
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Group 'wrong' was not found."

    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.devices.add(
            "black03", "black", "worker01", None, None, True, "wrong"
        )
    assert exc.value.faultCode == 400
    assert exc.value.faultString == "Invalid health"

    # 4. Generate an IntegrityError (same device name)
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.devices.add("black02", "black", "worker01")
    assert exc.value.faultCode == 400
    assert exc.value.faultString == "Bad request: device already exists?"


@pytest.mark.django_db
def test_devices_get_dictionary(setup, monkeypatch):
    # 1. no device
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.devices.get_dictionary("device01")
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Device 'device01' was not found."

    # 2. device is not visible to anonymous
    dt = DeviceType.objects.create(name="black")
    device = Device.objects.create(hostname="device01", device_type=dt, is_public=False)
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.devices.get_dictionary("device01")
    assert exc.value.faultCode == 403
    assert (
        exc.value.faultString
        == "Device 'device01' not available to user 'AnonymousUser'."
    )

    device.is_public = True
    device.save()

    # 3. invalid context
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.devices.get_dictionary("device01", True, "{{")
    assert exc.value.faultCode == 400
    assert exc.value.faultString.startswith("Job Context '{{' is not valid: ")

    # 4. no device dict
    monkeypatch.setattr(
        Device, "load_configuration", (lambda self, job_ctx, output_format: None)
    )
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.devices.get_dictionary("device01")
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Device 'device01' does not have a configuration"

    # 5. success
    monkeypatch.setattr(
        Device,
        "load_configuration",
        (lambda self, job_ctx, output_format: "device: dict"),
    )
    assert str(server().scheduler.devices.get_dictionary("device01")) == "device: dict"


@pytest.mark.django_db
def test_tags_add(setup):
    # 1. as anonymous => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.tags.add("hdd")
    assert exc.value.faultCode == 401
    assert (
        exc.value.faultString
        == "Authentication with user and token required for this API."
    )
    assert Tag.objects.count() == 0

    # 2. as user => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("user", "user").scheduler.tags.add("hdd")
    assert exc.value.faultCode == 403
    assert (
        exc.value.faultString
        == "User 'user' is missing permission lava_scheduler_app.add_tag ."
    )
    assert Tag.objects.count() == 0

    # 3. as admin => success
    assert server("admin", "admin").scheduler.tags.add("hdd") is None
    assert Tag.objects.count() == 1
    assert Tag.objects.all()[0].name == "hdd"
    assert Tag.objects.all()[0].description is None

    # 4. as admin set description => success
    assert server("admin", "admin").scheduler.tags.add("audio", "audio capture") is None
    assert Tag.objects.count() == 2
    assert Tag.objects.all()[1].name == "audio"
    assert Tag.objects.all()[1].description == "audio capture"

    # 5. already used name => exception
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.tags.add("hdd")
    assert exc.value.faultCode == 400
    assert exc.value.faultString == "Bad request: tag already exists?"


@pytest.mark.django_db
def test_tags_delete(setup):
    Tag.objects.create(name="hdd")
    Tag.objects.create(name="audio", description="audio capture")

    server("admin", "admin").scheduler.tags.delete("hdd")
    assert Tag.objects.count() == 1
    assert Tag.objects.all()[0].name == "audio"

    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.tags.delete("hdd")
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Tag 'hdd' was not found."

    server("admin", "admin").scheduler.tags.delete("audio")
    assert Tag.objects.count() == 0


@pytest.mark.django_db
def test_tags_show(setup):
    tag1 = Tag.objects.create(name="hdd")
    tag2 = Tag.objects.create(name="audio", description="audio capture")

    data = server().scheduler.tags.show("hdd")
    assert data == {"name": "hdd", "description": None, "devices": []}

    # Create some devices
    dt = DeviceType.objects.create(name="dt-01")
    device = Device.objects.create(hostname="d-01", device_type=dt, is_public=True)
    device.tags.add(tag1)

    data = server().scheduler.tags.show("hdd")
    assert data == {"name": "hdd", "description": None, "devices": ["d-01"]}

    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.tags.show("ssd")
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Tag 'ssd' was not found."


@pytest.mark.django_db
def test_tags_list(setup):
    data = server().scheduler.tags.list()
    assert data == []

    Tag.objects.create(name="hdd")
    data = server().scheduler.tags.list()
    assert data == [{"name": "hdd", "description": None}]

    Tag.objects.create(name="audio", description="audio capture")
    data = server().scheduler.tags.list()
    assert data == [
        {"name": "audio", "description": "audio capture"},
        {"name": "hdd", "description": None},
    ]


@pytest.mark.django_db
def test_workers_add(setup):
    # 1. as anonymous => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.workers.add("dispatcher.example.com")
    assert exc.value.faultCode == 401
    assert (
        exc.value.faultString
        == "Authentication with user and token required for this API."
    )
    assert Worker.objects.count() == 1  # "example.com" is part of the migrations

    # 2. as user => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("user", "user").scheduler.workers.add("dispatcher.example.com")
    assert exc.value.faultCode == 403
    assert (
        exc.value.faultString
        == "User 'user' is missing permission lava_scheduler_app.add_worker ."
    )
    assert Worker.objects.count() == 1  # "example.com" is part of the migrations

    # 3. as admin => success
    assert (
        server("admin", "admin").scheduler.workers.add("dispatcher.example.com") is None
    )
    assert Worker.objects.count() == 2
    assert Worker.objects.all()[1].hostname == "dispatcher.example.com"
    assert Worker.objects.all()[1].description is None
    assert Worker.objects.all()[1].health == Worker.HEALTH_ACTIVE

    # 4. as admin set description and health => success
    assert (
        server("admin", "admin").scheduler.workers.add(
            "worker.example.com", "worker", True
        )
        is None
    )
    assert Worker.objects.count() == 3
    assert Worker.objects.all()[2].hostname == "worker.example.com"
    assert Worker.objects.all()[2].description == "worker"
    assert Worker.objects.all()[2].health == Worker.HEALTH_RETIRED

    # 5. already used hostname => exception
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.add("dispatcher.example.com")
    assert exc.value.faultCode == 400
    assert exc.value.faultString == "Bad request: worker already exists?"


@pytest.mark.django_db
def test_workers_get_config_old_config(setup, monkeypatch, tmpdir):
    (tmpdir / "example.com.yaml").write_text("hello", encoding="utf-8")

    class MyPath(pathlib.PosixPath):
        def __new__(cls, path, *args, **kwargs):
            if path == "example.com":
                return super().__new__(cls, path, *args, **kwargs)
            elif path == "/etc/lava-server/dispatcher.d":
                return super().__new__(cls, str(tmpdir), *args, **kwargs)
            else:
                assert 0

    monkeypatch.setattr(pathlib, "Path", MyPath)
    assert (
        str(server("admin", "admin").scheduler.workers.get_config("example.com"))
        == "hello"
    )


@pytest.mark.django_db
def test_workers_get_config_new_config(setup, monkeypatch, tmpdir):
    (tmpdir / "example.com").mkdir()
    (tmpdir / "example.com" / "dispatcher.yaml").write_text(
        "hello world", encoding="utf-8"
    )

    class MyPath(pathlib.PosixPath):
        def __new__(cls, path, *args, **kwargs):
            if path == "example.com":
                return super().__new__(cls, path, *args, **kwargs)
            elif path == "/etc/lava-server/dispatcher.d":
                return super().__new__(cls, str(tmpdir), *args, **kwargs)
            elif path == "/etc/lava-server/dispatcher.d/example.com":
                return super().__new__(
                    cls, str(tmpdir / "example.com"), *args, **kwargs
                )
            else:
                assert 0

    monkeypatch.setattr(pathlib, "Path", MyPath)
    assert (
        str(server("admin", "admin").scheduler.workers.get_config("example.com"))
        == "hello world"
    )


@pytest.mark.django_db
def test_workers_get_config_exceptions(setup, monkeypatch, tmpdir):
    class MyPath(pathlib.PosixPath):
        def __new__(cls, path, *args, **kwargs):
            if path in ["example.com", "example.com/../", "worker.example.com"]:
                return super().__new__(cls, path, *args, **kwargs)
            elif path == "/etc/lava-server/dispatcher.d":
                return super().__new__(cls, str(tmpdir), *args, **kwargs)
            else:
                assert path == 0

    monkeypatch.setattr(pathlib, "Path", MyPath)

    # 1. invalid worker name (should not be a path)
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.get_config("example.com/../")
    assert exc.value.faultCode == 400
    assert exc.value.faultString == "Invalid worker name"

    # 2. worker does not exists
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.get_config("worker.example.com")
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Worker 'worker.example.com' was not found."

    # 3. no configuration file
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.get_config("example.com")
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Worker 'example.com' does not have a configuration"


@pytest.mark.django_db
def test_workers_get_env_old_config(setup, monkeypatch, tmpdir):
    (tmpdir / "env.yaml").write_text("hello", encoding="utf-8")

    class MyPath(pathlib.PosixPath):
        def __new__(cls, path, *args, **kwargs):
            if path == "example.com":
                return super().__new__(cls, path, *args, **kwargs)
            elif path == "/etc/lava-server/":
                return super().__new__(cls, str(tmpdir), *args, **kwargs)
            else:
                assert 0

    monkeypatch.setattr(pathlib, "Path", MyPath)
    assert (
        str(server("admin", "admin").scheduler.workers.get_env("example.com"))
        == "hello"
    )


@pytest.mark.django_db
def test_workers_get_env_new_config(setup, monkeypatch, tmpdir):
    (tmpdir / "dispatcher.d").mkdir()
    (tmpdir / "dispatcher.d" / "example.com").mkdir()
    (tmpdir / "dispatcher.d" / "example.com" / "env.yaml").write_text(
        "hello world", encoding="utf-8"
    )

    class MyPath(pathlib.PosixPath):
        def __new__(cls, path, *args, **kwargs):
            if path == "example.com":
                return super().__new__(cls, path, *args, **kwargs)
            elif path == "/etc/lava-server/":
                return super().__new__(cls, str(tmpdir), *args, **kwargs)
            else:
                assert 0

    monkeypatch.setattr(pathlib, "Path", MyPath)
    assert (
        str(server("admin", "admin").scheduler.workers.get_env("example.com"))
        == "hello world"
    )


@pytest.mark.django_db
def test_workers_get_env_exceptions(setup, monkeypatch, tmpdir):
    class MyPath(pathlib.PosixPath):
        def __new__(cls, path, *args, **kwargs):
            if path in ["example.com", "example.com/../", "worker.example.com"]:
                return super().__new__(cls, path, *args, **kwargs)
            elif path == "/etc/lava-server/":
                return super().__new__(cls, str(tmpdir), *args, **kwargs)
            else:
                assert path == 0

    monkeypatch.setattr(pathlib, "Path", MyPath)

    # 1. invalid worker name (should not be a path)
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.get_env("example.com/../")
    assert exc.value.faultCode == 400
    assert exc.value.faultString == "Invalid worker name"

    # 2. worker does not exists
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.get_env("worker.example.com")
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Worker 'worker.example.com' was not found."

    # 3. no configuration file
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.get_env("example.com")
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Worker 'example.com' does not have a configuration"


@pytest.mark.django_db
def test_workers_set_config(setup, monkeypatch, tmpdir):
    class MyPath(pathlib.PosixPath):
        def __new__(cls, path, *args, **kwargs):
            if path == "example.com":
                return super().__new__(cls, path, *args, **kwargs)
            elif path == "/etc/lava-server/dispatcher.d":
                return super().__new__(cls, str(tmpdir), *args, **kwargs)
            else:
                assert 0

    monkeypatch.setattr(pathlib, "Path", MyPath)
    assert (
        server("admin", "admin").scheduler.workers.set_config("example.com", "hello")
        is True
    )
    assert (tmpdir / "example.com" / "dispatcher.yaml").read_text(
        encoding="utf-8"
    ) == "hello"


@pytest.mark.django_db
def test_workers_set_config_exceptions(setup, monkeypatch, tmpdir):
    class MyPath(pathlib.PosixPath):
        def __new__(cls, path, *args, **kwargs):
            if path in ["example.com", "example.com/../", "worker.example.com"]:
                return super().__new__(cls, path, *args, **kwargs)
            elif path == "/etc/lava-server/dispatcher.d":
                return super().__new__(cls, str(tmpdir), *args, **kwargs)
            else:
                assert path == 0

    monkeypatch.setattr(pathlib, "Path", MyPath)

    # 1. invalid worker name (should not be a path)
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.set_config(
            "example.com/../", "error"
        )
    assert exc.value.faultCode == 400
    assert exc.value.faultString == "Invalid worker name"

    # 2. worker does not exists
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.set_config(
            "worker.example.com", "error"
        )
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Worker 'worker.example.com' was not found."
    # 3. as user => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("user", "user").scheduler.workers.set_config(
            "worker.example.com", "error"
        )
    assert exc.value.faultCode == 403
    assert (
        exc.value.faultString
        == "User 'user' is missing permission lava_scheduler_app.change_worker ."
    )


@pytest.mark.django_db
def test_workers_set_env(setup, monkeypatch, tmpdir):
    class MyPath(pathlib.PosixPath):
        def __new__(cls, path, *args, **kwargs):
            if path == "example.com":
                return super().__new__(cls, path, *args, **kwargs)
            elif path == "/etc/lava-server/dispatcher.d":
                return super().__new__(cls, str(tmpdir), *args, **kwargs)
            else:
                assert 0

    monkeypatch.setattr(pathlib, "Path", MyPath)
    assert (
        server("admin", "admin").scheduler.workers.set_env("example.com", "hello")
        is True
    )
    assert (tmpdir / "example.com" / "env.yaml").read_text(encoding="utf-8") == "hello"


@pytest.mark.django_db
def test_workers_set_env_exceptions(setup, monkeypatch, tmpdir):
    class MyPath(pathlib.PosixPath):
        def __new__(cls, path, *args, **kwargs):
            if path in ["example.com", "example.com/../", "worker.example.com"]:
                return super().__new__(cls, path, *args, **kwargs)
            elif path == "/etc/lava-server/dispatcher.d":
                return super().__new__(cls, str(tmpdir), *args, **kwargs)
            else:
                assert path == 0

    monkeypatch.setattr(pathlib, "Path", MyPath)

    # 1. invalid worker name (should not be a path)
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.set_env("example.com/../", "error")
    assert exc.value.faultCode == 400
    assert exc.value.faultString == "Invalid worker name"

    # 2. worker does not exists
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.set_env(
            "worker.example.com", "error"
        )
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Worker 'worker.example.com' was not found."
    # 3. as user => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("user", "user").scheduler.workers.set_env("worker.example.com", "error")
    assert exc.value.faultCode == 403
    assert (
        exc.value.faultString
        == "User 'user' is missing permission lava_scheduler_app.change_worker ."
    )


@pytest.mark.django_db
def test_workers_list(setup):
    data = server().scheduler.workers.list()
    assert data == ["example.com"]

    Worker.objects.create(hostname="worker01")
    data = server().scheduler.workers.list()
    assert data == ["example.com", "worker01"]


@pytest.mark.django_db
def test_workers_show(setup):
    data = server().scheduler.workers.show("example.com")
    assert set(data.keys()) == set(
        ["hostname", "description", "state", "health", "devices", "last_ping"]
    )
    assert data["hostname"] == "example.com"

    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.workers.show("bla")
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Worker 'bla' was not found."


@pytest.mark.django_db
def test_workers_update(setup):
    # 1. as anonymous => failure
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.workers.update("example.com")
    assert exc.value.faultCode == 401
    assert (
        exc.value.faultString
        == "Authentication with user and token required for this API."
    )

    # 2. as user => failure
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("user", "user").scheduler.workers.update("example.com")
    assert exc.value.faultCode == 403
    assert (
        exc.value.faultString
        == "User 'user' is missing permission lava_scheduler_app.change_worker ."
    )

    # 3. as admin
    assert server("admin", "admin").scheduler.workers.update("example.com") is None
    assert Worker.objects.get(hostname="example.com").description is None
    assert Worker.objects.get(hostname="example.com").health == Worker.HEALTH_ACTIVE

    assert (
        server("admin", "admin").scheduler.workers.update("example.com", "dummy worker")
        is None
    )
    assert Worker.objects.get(hostname="example.com").description == "dummy worker"
    assert Worker.objects.get(hostname="example.com").health == Worker.HEALTH_ACTIVE

    assert (
        server("admin", "admin").scheduler.workers.update(
            "example.com", None, "MAINTENANCE"
        )
        is None
    )
    assert Worker.objects.get(hostname="example.com").description == "dummy worker"
    assert (
        Worker.objects.get(hostname="example.com").health == Worker.HEALTH_MAINTENANCE
    )
    assert (
        server("admin", "admin").scheduler.workers.update(
            "example.com", None, "RETIRED"
        )
        is None
    )
    assert Worker.objects.get(hostname="example.com").health == Worker.HEALTH_RETIRED
    assert (
        server("admin", "admin").scheduler.workers.update("example.com", None, "ACTIVE")
        is None
    )
    assert Worker.objects.get(hostname="example.com").health == Worker.HEALTH_ACTIVE

    # worker does not exists
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.update("something")
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Worker 'something' was not found."

    # invalid health
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.update("example.com", None, "wrong")
    assert exc.value.faultCode == 400
    assert exc.value.faultString == "Invalid health: wrong"
