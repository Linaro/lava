import unittest
import xmlrpc.client
from io import BytesIO as StringIO

import pytest
from django.contrib.auth.models import Group, Permission, User
from django.test.client import Client

from lava_common.decorators import nottest
from lava_common.yaml import yaml_safe_load
from lava_scheduler_app.dbutils import validate_yaml
from lava_scheduler_app.models import (
    Alias,
    Device,
    DeviceType,
    GroupDevicePermission,
    GroupDeviceTypePermission,
    Tag,
    Worker,
)
from lava_scheduler_app.schema import SubmissionException, validate_submission
from tests.lava_scheduler_app.test_submission import TestCaseWithFactory


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


class TestSchedulerAPI(TestCaseWithFactory):
    def server_proxy(self, user=None, password=None):
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
            self.assertEqual(400, f.faultCode)
        else:
            self.fail("fault not raised")

    def test_new_devices(self):
        user = self.factory.ensure_user("test", "e@mail.invalid", "test")
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
    def test_breakage_detection(self):
        bad_submission = """
timeouts:
  job:
    minutes: 15
  action:
    minutes: 5
                """
        self.assertRaises(
            SubmissionException, validate_submission, yaml_safe_load(bad_submission)
        )
        try:
            validate_submission(yaml_safe_load(bad_submission))
        except SubmissionException as exc:
            # with more than one omission, which one gets mentioned is undefined
            self.assertIn("required key not provided", str(exc))
        bad_submission += """
actions:
  - deploy:
      to: tmpfs
                """
        self.assertRaises(
            SubmissionException, validate_submission, yaml_safe_load(bad_submission)
        )
        try:
            validate_submission(yaml_safe_load(bad_submission))
        except SubmissionException as exc:
            self.assertIn("required key not provided", str(exc))
            # with more than one omission, which one gets mentioned is undefined
            self.assertTrue("visibility" in str(exc) or "job_name" in str(exc))
        bad_submission += """
visibility: public
                """
        self.assertRaises(
            SubmissionException, validate_submission, yaml_safe_load(bad_submission)
        )
        try:
            validate_submission(yaml_safe_load(bad_submission))
        except SubmissionException as exc:
            self.assertIn("required key not provided", str(exc))
            self.assertIn("job_name", str(exc))
        bad_submission += """
job_name: qemu-pipeline
                """
        self.assertTrue(validate_submission(yaml_safe_load(bad_submission)))
        bad_yaml = yaml_safe_load(bad_submission)
        del bad_yaml["timeouts"]["job"]
        try:
            validate_submission(yaml_safe_load(bad_submission))
        except SubmissionException as exc:
            self.assertIn("required key not provided", str(exc))
            self.assertIn("job", str(exc))
            self.assertIn("timeouts", str(exc))
        bad_submission += """
notify:
  criteria:
    status: complete
        """
        self.assertTrue(validate_submission(yaml_safe_load(bad_submission)))
        bad_submission += """
  compare:
    query:
      entity: testrunfilter
        """
        self.assertRaises(
            SubmissionException, validate_yaml, yaml_safe_load(bad_submission)
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
            yaml_safe_load(invalid_monitors_name_char_yaml_def),
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
            validate_submission(yaml_safe_load(bad_submission))
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
            validate_submission(yaml_safe_load(bad_submission))
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
        self.assertTrue(validate_submission(yaml_safe_load(secrets)))
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
        self.assertTrue(validate_submission(yaml_safe_load(secrets)))

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
        self.assertTrue(validate_submission(yaml_safe_load(data)))

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
        self.assertTrue(validate_submission(yaml_safe_load(data)))

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
        self.assertTrue(validate_submission(yaml_safe_load(data)))

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
        self.assertTrue(validate_submission(yaml_safe_load(data)))

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
            SubmissionException, validate_submission, yaml_safe_load(data)
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
            SubmissionException, validate_submission, yaml_safe_load(data)
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
            SubmissionException, validate_submission, yaml_safe_load(data)
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
            SubmissionException, validate_submission, yaml_safe_load(data)
        )


@pytest.fixture
def setup(db):
    user = User.objects.create_user(username="user", password="user")  # nosec
    group = Group.objects.create(name="group")
    admin = User.objects.create_user(
        username="admin", password="admin", is_superuser=True
    )  # nosec
    staff = User.objects.create_user(
        username="staff", password="staff", is_staff=True, is_superuser=False
    )
    user.user_permissions.add(Permission.objects.get(codename="add_alias"))
    user.user_permissions.add(Permission.objects.get(codename="delete_alias"))


def server(user=None, password=None):
    return xmlrpc.client.ServerProxy(
        "http://localhost/RPC2/",
        transport=TestTransport(user=user, password=password),
        allow_none=True,
    )


@pytest.mark.django_db
def test_aliases_add(setup):
    # 1. existing device-type not-visible
    dt = DeviceType.objects.create(name="qemu")
    group = Group.objects.create(name="group1")
    GroupDeviceTypePermission.objects.assign_perm("view_devicetype", group, dt)
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("user", "user").scheduler.aliases.add("kvm", "qemu")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "Device-type 'qemu' was not found."  # nosec
    assert Alias.objects.count() == 0  # nosec
    GroupDeviceTypePermission.objects.remove_perm("view_devicetype", group, dt)

    # 2. existing device-type visible
    device = Device.objects.create(hostname="device01", device_type=dt)
    assert (  # nosec
        server("admin", "admin").scheduler.aliases.add("kvm", "qemu") is None
    )
    assert Alias.objects.count() == 1  # nosec
    assert Alias.objects.all()[0].name == "kvm"  # nosec
    assert Alias.objects.all()[0].device_type.name == "qemu"  # nosec

    # 2. non-existing device-type
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.aliases.add("kvm", "emu")
    assert exc.value.faultCode == 400  # nosec
    assert exc.value.faultString == "Bad request. DeviceType does not exist"  # nosec

    assert Alias.objects.count() == 1  # nosec

    # 3. the tag name is used by a device-type
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.aliases.add("qemu", "qemu")
    assert exc.value.faultCode == 404  # nosec
    assert (  # nosec
        exc.value.faultString == "DeviceType with name 'qemu' already exists."
    )

    # 4. the alias already exists
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.aliases.add("kvm", "qemu")
    assert exc.value.faultCode == 404  # nosec
    assert (  # nosec
        exc.value.faultString
        == "Alias with this Alias for this device-type already exists."
    )


@pytest.mark.django_db
def test_aliases_delete(setup):
    dt = DeviceType.objects.create(name="qemu")
    alias = Alias.objects.create(name="kvm", device_type=dt)
    assert server("admin", "admin").scheduler.aliases.delete("kvm") is None  # nosec
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.aliases.delete("kvm")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "Alias 'kvm' was not found."  # nosec


@pytest.mark.django_db
def test_aliases_list(setup):
    dt = DeviceType.objects.create(name="qemu")
    alias = Alias.objects.create(name="kvm", device_type=dt)
    assert server().scheduler.aliases.list() == ["kvm"]  # nosec


@pytest.mark.django_db
def test_aliases_show(setup):
    dt = DeviceType.objects.create(name="qemu")
    alias = Alias.objects.create(name="kvm", device_type=dt)
    assert server().scheduler.aliases.show("kvm") == {  # nosec
        "name": "kvm",
        "device_type": "qemu",
    }

    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.aliases.show("cubie")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "Alias 'cubie' was not found."  # nosec


@pytest.mark.django_db
def test_devices_add(setup):
    # 1. missing device-type and worker
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.devices.add("black01", "black", "worker01")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "DeviceType 'black' was not found."  # nosec

    # Create the device-type
    DeviceType.objects.create(name="black")
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.devices.add("black01", "black", "worker01")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "Worker 'worker01' was not found."  # nosec

    Worker.objects.create(hostname="worker01")
    server("admin", "admin").scheduler.devices.add("black01", "black", "worker01")
    Device.objects.count() == 1
    Device.objects.all()[0].hostname == "black01"
    Device.objects.all()[0].device_type.name == "black"
    Device.objects.all()[0].worker_host.hostname == "worker01"
    Device.objects.all()[0].get_health_display() == "Unknown"

    # 2. test description, health
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
    Device.objects.all()[1].get_health_display() == "Maintenance"

    # 3. wrong health
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.devices.add(
            "black03", "black", "worker01", None, None, True, "wrong"
        )
    assert exc.value.faultCode == 400  # nosec
    assert exc.value.faultString == "Invalid health"  # nosec

    # 4. Generate an IntegrityError (same device name)
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.devices.add("black02", "black", "worker01")
    assert exc.value.faultCode == 400  # nosec
    assert exc.value.faultString == "Bad request: device already exists?"  # nosec


def test_devices_delete(setup):
    dt = DeviceType.objects.create(name="black")
    Device.objects.create(hostname="device01", device_type=dt)

    # 1. as anonymous => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        # "example.com" is part of the migrations
        server().scheduler.devices.delete("device01")
    assert exc.value.faultCode == 401
    assert (
        exc.value.faultString
        == "Authentication with user and token required for this API."
    )
    assert Device.objects.count() == 1

    # 2. as user => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("user", "user").scheduler.devices.delete("device01")
    assert exc.value.faultCode == 403
    assert (
        exc.value.faultString
        == "User 'user' is missing permission lava_scheduler_app.delete_device."
    )
    assert Device.objects.count() == 1

    # 3. as admin => success
    assert server("admin", "admin").scheduler.devices.delete("device01") is None
    assert Device.objects.count() == 0

    # 4. device does not exists => 404
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.devices.delete("device01")
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Device 'device01' was not found."


@pytest.mark.django_db
def test_devices_get_dictionary(setup, monkeypatch):
    # 1. no device
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.devices.get_dictionary("device01")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "Device 'device01' was not found."  # nosec

    # 2. device is not visible to anonymous
    dt = DeviceType.objects.create(name="black")
    device = Device.objects.create(hostname="device01", device_type=dt)
    group = Group.objects.create(name="group1")
    GroupDevicePermission.objects.assign_perm("view_device", group, device)
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.devices.get_dictionary("device01")
    assert exc.value.faultCode == 403  # nosec
    assert (  # nosec
        exc.value.faultString
        == "Device 'device01' not available to user 'AnonymousUser'."
    )
    GroupDevicePermission.objects.remove_perm("view_device", group, device)

    # 3. invalid context
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.devices.get_dictionary("device01", True, "{{")
    assert exc.value.faultCode == 400  # nosec
    assert exc.value.faultString.startswith("Job Context '{{' is not valid: ")  # nosec

    # 4. no device dict
    monkeypatch.setattr(
        Device, "load_configuration", (lambda self, job_ctx, output_format: None)
    )
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.devices.get_dictionary("device01")
    assert exc.value.faultCode == 404  # nosec
    assert (  # nosec
        exc.value.faultString == "Device 'device01' does not have a configuration"
    )

    # 5. success
    monkeypatch.setattr(
        Device,
        "load_configuration",
        (lambda self, job_ctx, output_format: "device: dict"),
    )
    assert (  # nosec
        str(server().scheduler.devices.get_dictionary("device01")) == "device: dict"
    )


@pytest.mark.django_db
def test_devices_set_dictionary(setup, monkeypatch):
    def save_configuration(self, data):
        assert data == "hello"  # nosec

    monkeypatch.setattr(Device, "save_configuration", save_configuration)

    # 1. device does not exists
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.devices.set_dictionary("device01", "hello")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString.startswith("Device 'device01' was not found.")  # nosec

    dt = DeviceType.objects.create(name="black")
    device = Device.objects.create(hostname="device01", device_type=dt)
    assert (  # nosec
        server("admin", "admin").scheduler.devices.set_dictionary("device01", "hello")
        is None
    )


@pytest.mark.django_db
def test_devices_list(setup):
    assert server().scheduler.devices.list() == []  # nosec

    dt = DeviceType.objects.create(name="black")
    device1 = Device.objects.create(hostname="device01", device_type=dt)
    device2 = Device.objects.create(hostname="device02", device_type=dt)
    group = Group.objects.create(name="group1")
    GroupDevicePermission.objects.assign_perm("view_device", group, device2)
    assert server().scheduler.devices.list() == [  # nosec
        {
            "current_job": None,
            "health": "Maintenance",
            "hostname": "device01",
            "pipeline": True,
            "state": "Idle",
            "type": "black",
        }
    ]


@pytest.mark.django_db
def test_device_perms_add(setup):
    dt = DeviceType.objects.create(name="dt-01")
    device = Device.objects.create(hostname="d-01", device_type=dt)

    # 1. as anonymous => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.devices.perms_add("d-01", "group", "change_device")
    assert exc.value.faultCode == 401
    assert (
        exc.value.faultString
        == "Authentication with user and token required for this API."
    )
    assert GroupDevicePermission.objects.filter(device=device).count() == 0

    # 2. as user => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("user", "user").scheduler.devices.perms_add(
            "d-01", "group", "change_device"
        )
    assert exc.value.faultCode == 403
    assert exc.value.faultString == "forbidden"
    assert GroupDevicePermission.objects.filter(device=device).count() == 0

    # 3. as staff => success
    server("staff", "staff").scheduler.devices.perms_add(
        "d-01", "group", "change_device"
    )
    group_device_perms = GroupDevicePermission.objects.filter(device=device)
    assert group_device_perms.count() == 1
    group_device_perm = GroupDevicePermission.objects.filter(device=device)[0]
    assert group_device_perm.device.hostname == "d-01"
    assert group_device_perm.group.name == "group"
    assert group_device_perm.permission.codename == "change_device"

    # 4. device does not exist
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("staff", "staff").scheduler.devices.perms_add(
            "d-02", "group", "change_device"
        )
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Device 'd-02' was not found."

    # 5. group does not exist
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("staff", "staff").scheduler.devices.perms_add(
            "d-01", "group11", "change_device"
        )
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Group 'group11' was not found."


@pytest.mark.django_db
def test_device_perms_delete(setup):
    dt = DeviceType.objects.create(name="dt-01")
    device = Device.objects.create(hostname="d-01", device_type=dt)
    GroupDevicePermission.objects.assign_perm(
        "change_device", Group.objects.get(name="group"), device
    )

    # 1. as anonymous => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.devices.perms_delete("d-01", "group", "change_device")
    assert exc.value.faultCode == 401
    assert (
        exc.value.faultString
        == "Authentication with user and token required for this API."
    )
    assert GroupDevicePermission.objects.filter(device=device).count() == 1

    # 2. as user => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("user", "user").scheduler.devices.perms_delete(
            "d-01", "group", "change_device"
        )
    assert exc.value.faultCode == 403
    assert exc.value.faultString == "forbidden"
    assert GroupDevicePermission.objects.filter(device=device).count() == 1

    # 3. as staff => success
    server("staff", "staff").scheduler.devices.perms_delete(
        "d-01", "group", "change_device"
    )
    assert GroupDevicePermission.objects.filter(device=device).count() == 0

    # 4. device does not exist
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("staff", "staff").scheduler.devices.perms_delete(
            "d-02", "group", "change_device"
        )
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Device 'd-02' was not found."

    # 5. group does not exist
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("staff", "staff").scheduler.devices.perms_delete(
            "d-01", "group11", "change_device"
        )
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Group 'group11' was not found."


@pytest.mark.django_db
def test_device_perms_list(setup):
    dt = DeviceType.objects.create(name="dt-01")
    device = Device.objects.create(hostname="d-01", device_type=dt)

    # 1. as anonymous => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.devices.perms_list("d-01")
    assert exc.value.faultCode == 401
    assert (
        exc.value.faultString
        == "Authentication with user and token required for this API."
    )

    # 2. as user => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("user", "user").scheduler.devices.perms_list("d-01")
    assert exc.value.faultCode == 403
    assert exc.value.faultString == "forbidden"

    # 3. as staff => success.
    perms = server("staff", "staff").scheduler.devices.perms_list("d-01")
    assert perms == []
    GroupDevicePermission.objects.assign_perm(
        "change_device", Group.objects.get(name="group"), device
    )
    perms = server("staff", "staff").scheduler.devices.perms_list("d-01")
    assert len(perms) == 1
    assert perms[0]["name"] == "change_device"
    assert perms[0]["group"] == "group"

    # 4. device does not exist
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("staff", "staff").scheduler.devices.perms_list("d-02")
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Device 'd-02' was not found."


@pytest.mark.django_db
def test_devices_show(setup):
    assert server().scheduler.devices.list() == []  # nosec

    dt = DeviceType.objects.create(name="black")
    device1 = Device.objects.create(hostname="device01", device_type=dt)
    device2 = Device.objects.create(hostname="device02", device_type=dt)
    group = Group.objects.create(name="group1")
    GroupDevicePermission.objects.assign_perm("view_device", group, device2)

    # 1. device does not exist
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.devices.show("device00")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "Device 'device00' was not found."  # nosec

    # 2. device not visible
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.devices.show("device02")
    assert exc.value.faultCode == 403  # nosec
    assert (  # nosec
        exc.value.faultString
        == "Device 'device02' not available to user 'AnonymousUser'."
    )

    # 3. normal device
    data = server().scheduler.devices.show("device01")
    assert data == {  # nosec
        "current_job": None,
        "description": None,
        "device_type": "black",
        "has_device_dict": False,
        "health": "Maintenance",
        "health_job": False,
        "hostname": "device01",
        "pipeline": True,
        "state": "Idle",
        "tags": [],
        "worker": None,
        "permissions": [],
    }

    # 4. add a worker
    worker = Worker.objects.create(hostname="worker01")
    device1.worker_host = worker
    device1.save()
    data = server().scheduler.devices.show("device01")
    assert data == {  # nosec
        "current_job": None,
        "description": None,
        "device_type": "black",
        "has_device_dict": False,
        "health": "Maintenance",
        "health_job": False,
        "hostname": "device01",
        "pipeline": True,
        "state": "Idle",
        "tags": [],
        "worker": "worker01",
        "permissions": [],
    }

    # 5. Add a group permission.
    GroupDevicePermission.objects.assign_perm("change_device", group, device1)
    data = server().scheduler.devices.show("device01")
    assert data == {
        "current_job": None,
        "description": None,
        "device_type": "black",
        "has_device_dict": False,
        "health": "Maintenance",
        "health_job": False,
        "hostname": "device01",
        "pipeline": True,
        "state": "Idle",
        "tags": [],
        "worker": "worker01",
        "permissions": [
            {"name": "change_device", "group": "group1"},
        ],
    }


@pytest.mark.django_db
def test_devices_update(setup):
    # 1. missing device-type and worker
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.devices.update("black01", "worker01")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "Device 'black01' was not found."  # nosec

    dt = DeviceType.objects.create(name="black")
    device = Device.objects.create(hostname="black01", device_type=dt)

    # 2. update the worker (worker does not exist)
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.devices.update("black01", "worker01")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "Unable to find worker 'worker01'"  # nosec

    # 3. update the worker
    Worker.objects.create(hostname="worker01")
    server("admin", "admin").scheduler.devices.update("black01", "worker01")
    device.refresh_from_db()
    assert device.worker_host.hostname == "worker01"  # nosec

    # 4. update health (wrong value)
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.devices.update(
            "black01", None, None, None, None, "wrong"
        )
    assert exc.value.faultCode == 400  # nosec
    assert exc.value.faultString == "Health 'wrong' is invalid"  # nosec

    # 5. update health
    server("admin", "admin").scheduler.devices.update(
        "black01", None, None, None, None, "GOOD"
    )
    device.refresh_from_db()
    assert device.health == Device.HEALTH_GOOD  # nosec

    # 6. update description
    server("admin", "admin").scheduler.devices.update(
        "black01", None, None, None, None, None, "hello"
    )
    device.refresh_from_db()
    assert device.description == "hello"  # nosec


@pytest.mark.django_db
def test_devices_tags_add(setup):
    dt = DeviceType.objects.create(name="black")
    device = Device.objects.create(hostname="device01", device_type=dt)
    assert device.tags.count() == 0  # nosec

    # 1. device does not exist
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.devices.tags.add("black01", "hdd")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "Device 'black01' was not found."  # nosec

    # 2. add a tag
    server("admin", "admin").scheduler.devices.tags.add("device01", "hdd")
    device.refresh_from_db()
    assert device.tags.count() == 1  # nosec
    assert device.tags.all()[0].name == "hdd"  # nosec


@pytest.mark.django_db
def test_devices_tags_list(setup):
    dt = DeviceType.objects.create(name="black")
    device = Device.objects.create(hostname="device01", device_type=dt)
    tag = Tag.objects.create(name="hdd")
    device.tags.add(tag)
    device.refresh_from_db()
    assert device.tags.count() == 1  # nosec

    # 1. device does not exist
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.devices.tags.list("black01")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "Device 'black01' was not found."  # nosec

    # 2. list the tags
    data = server("admin", "admin").scheduler.devices.tags.list("device01")
    assert data == ["hdd"]  # nosec


@pytest.mark.django_db
def test_devices_tags_delete(setup):
    dt = DeviceType.objects.create(name="black")
    device = Device.objects.create(hostname="device01", device_type=dt)
    tag = Tag.objects.create(name="hdd")
    device.tags.add(tag)
    device.refresh_from_db()
    assert device.tags.count() == 1  # nosec

    # 1. device does not exist
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.devices.tags.delete("black01", "hdd")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "Device 'black01' was not found."  # nosec

    # 2. add a tag
    server("admin", "admin").scheduler.devices.tags.delete("device01", "hdd")
    device.refresh_from_db()
    assert device.tags.count() == 0  # nosec

    # 3. tag does not exist
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.devices.tags.delete("device01", "ssd")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "Tag 'ssd' was not found."  # nosec


@pytest.mark.django_db
def test_device_types_add(setup):
    # 1. Check that the arguments are used
    assert DeviceType.objects.count() == 0  # nosec
    server("admin", "admin").scheduler.device_types.add(
        "qemu", "emulated devices", True, None, 12, "hours"
    )
    assert DeviceType.objects.count() == 1  # nosec
    assert DeviceType.objects.all()[0].name == "qemu"  # nosec
    assert DeviceType.objects.all()[0].display  # nosec
    assert DeviceType.objects.all()[0].description == "emulated devices"  # nosec
    assert DeviceType.objects.all()[0].health_frequency == 12  # nosec
    assert (  # nosec
        DeviceType.objects.all()[0].health_denominator == DeviceType.HEALTH_PER_HOUR
    )

    server("admin", "admin").scheduler.device_types.add(
        "b2260", None, True, None, 12, "jobs"
    )
    assert DeviceType.objects.count() == 2  # nosec
    assert DeviceType.objects.all()[1].name == "b2260"  # nosec
    assert DeviceType.objects.all()[1].display  # nosec
    assert DeviceType.objects.all()[1].description is None  # nosec
    assert DeviceType.objects.all()[1].health_frequency == 12  # nosec
    assert (  # nosec
        DeviceType.objects.all()[1].health_denominator == DeviceType.HEALTH_PER_JOB
    )

    # 2. Invalid health_denominator
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.device_types.add(
            "docker", None, True, None, 12, "job"
        )
    assert exc.value.faultCode == 400  # nosec
    assert exc.value.faultString == "Bad request: invalid health_denominator."  # nosec

    # 3. Already exists
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.device_types.add(
            "b2260", None, True, None, 12, "jobs"
        )
    assert exc.value.faultCode == 400  # nosec
    assert (  # nosec
        exc.value.faultString == "Bad request: device-type name is already used."
    )


@pytest.mark.django_db
def test_device_types_get_health_check(setup, mocker, tmp_path):
    (tmp_path / "qemu.yaml").write_text("hello", encoding="utf-8")
    mocker.patch(
        "lava_server.files.File.KINDS",
        {"health-check": ([str(tmp_path)], "{name}.yaml")},
    )

    # 1. normal case
    DeviceType.objects.create(name="qemu")
    hc = server("admin", "admin").scheduler.device_types.get_health_check("qemu")
    assert str(hc) == "hello"  # nosec

    # 2. DeviceType does not exists
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.device_types.get_health_check("docker")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "Device-type 'docker' was not found."  # nosec

    # 3. Invalid name
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.device_types.get_health_check("../../passwd")
    assert exc.value.faultCode == 400  # nosec
    assert exc.value.faultString == "Invalid device-type '../../passwd'"  # nosec


@pytest.mark.django_db
def test_device_types_get_template(setup, mocker, tmp_path):
    (tmp_path / "qemu.jinja2").write_text("hello", encoding="utf-8")
    mocker.patch(
        "lava_server.files.File.KINDS",
        {"device-type": ([str(tmp_path)], "{name}.jinja2")},
    )

    # 1. normal case
    DeviceType.objects.create(name="qemu")
    hc = server("admin", "admin").scheduler.device_types.get_template("qemu")
    assert str(hc) == "hello"  # nosec

    # 2. DeviceType does not exists
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.device_types.get_template("docker")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "Device-type 'docker' was not found."  # nosec

    # 3. Invalid name
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.device_types.get_template("../../passwd")
    assert exc.value.faultCode == 400  # nosec
    assert exc.value.faultString == "Invalid device-type '../../passwd'"  # nosec


@pytest.mark.django_db
def test_device_types_set_health_check(setup, mocker, tmp_path):
    mocker.patch(
        "lava_server.files.File.KINDS",
        {"health-check": ([str(tmp_path)], "{name}.yaml")},
    )

    # 1. normal case
    DeviceType.objects.create(name="qemu")
    server("admin", "admin").scheduler.device_types.set_health_check(
        "qemu", "hello world"
    )
    assert (tmp_path / "qemu.yaml").read_text(
        encoding="utf-8"
    ) == "hello world"  # nosec

    # 2. Invalid name
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.device_types.set_health_check(
            "../../passwd", ""
        )
    assert exc.value.faultCode == 400  # nosec
    assert exc.value.faultString == "Invalid device-type '../../passwd'"  # nosec


@pytest.mark.django_db
def test_device_types_set_template(setup, mocker, tmp_path):
    mocker.patch(
        "lava_server.files.File.KINDS",
        {"device-type": ([str(tmp_path)], "{name}.jinja2")},
    )

    # 1. normal case
    DeviceType.objects.create(name="qemu")
    server("admin", "admin").scheduler.device_types.set_template("qemu", "hello world")
    assert (tmp_path / "qemu.jinja2").read_text(  # nosec
        encoding="utf-8"
    ) == "hello world"

    # 2. Invalid name
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.device_types.set_template("../../passwd", "")
    assert exc.value.faultCode == 400  # nosec
    assert exc.value.faultString == "Invalid device-type '../../passwd'"  # nosec


@pytest.mark.django_db
def test_device_types_list(setup, mocker, tmp_path):
    mocker.patch(
        "lava_server.files.File.KINDS",
        {"device-type": ([str(tmp_path)], "{name}.jinja2")},
    )
    (tmp_path / "base.jinja2").write_text("", encoding="utf-8")
    (tmp_path / "base-uboot.jinja2").write_text("", encoding="utf-8")
    (tmp_path / "b2260.jinja2").write_text("", encoding="utf-8")
    (tmp_path / "qemu.jinja2").write_text("", encoding="utf-8")

    data = server("admin", "admin").scheduler.device_types.list()
    assert data == []  # nosec

    DeviceType.objects.create(name="qemu")
    data = server("admin", "admin").scheduler.device_types.list()
    assert data == [  # nosec
        {"name": "qemu", "devices": 0, "installed": True, "template": True}
    ]

    data = server("admin", "admin").scheduler.device_types.list(True)
    assert data == [  # nosec
        {"name": "qemu", "devices": 0, "installed": True, "template": True},
        {"name": "b2260", "devices": 0, "installed": False, "template": True},
    ]


@pytest.mark.django_db
def test_device_types_perms_add(setup):
    dt = DeviceType.objects.create(name="dt-01")

    # 1. as anonymous => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.device_types.perms_add("dt-01", "group", "change_devicetype")
    assert exc.value.faultCode == 401
    assert (
        exc.value.faultString
        == "Authentication with user and token required for this API."
    )
    assert GroupDeviceTypePermission.objects.filter(devicetype=dt).count() == 0

    # 2. as user => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("user", "user").scheduler.device_types.perms_add(
            "dt-01", "group", "change_devicetype"
        )
    assert exc.value.faultCode == 403
    assert exc.value.faultString == "forbidden"
    assert GroupDeviceTypePermission.objects.filter(devicetype=dt).count() == 0

    # 3. as staff => success
    server("staff", "staff").scheduler.device_types.perms_add(
        "dt-01", "group", "change_devicetype"
    )
    group_dt_perms = GroupDeviceTypePermission.objects.filter(devicetype=dt)
    assert group_dt_perms.count() == 1
    group_dt_perm = GroupDeviceTypePermission.objects.filter(devicetype=dt)[0]
    assert group_dt_perm.devicetype.name == "dt-01"
    assert group_dt_perm.group.name == "group"
    assert group_dt_perm.permission.codename == "change_devicetype"

    # 4. device-type does not exist
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("staff", "staff").scheduler.device_types.perms_add(
            "dt-02", "group", "change_devicetype"
        )
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Device-type 'dt-02' was not found."

    # 5. group does not exist
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("staff", "staff").scheduler.device_types.perms_add(
            "dt-01", "group11", "change_devicetype"
        )
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Group 'group11' was not found."


@pytest.mark.django_db
def test_device_types_perms_delete(setup):
    dt = DeviceType.objects.create(name="dt-01")
    GroupDeviceTypePermission.objects.assign_perm(
        "change_devicetype", Group.objects.get(name="group"), dt
    )

    # 1. as anonymous => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.device_types.perms_delete(
            "dt-01", "group", "change_devicetype"
        )
    assert exc.value.faultCode == 401
    assert (
        exc.value.faultString
        == "Authentication with user and token required for this API."
    )
    assert GroupDeviceTypePermission.objects.filter(devicetype=dt).count() == 1

    # 2. as user => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("user", "user").scheduler.device_types.perms_delete(
            "dt-01", "group", "change_devicetype"
        )
    assert exc.value.faultCode == 403
    assert exc.value.faultString == "forbidden"
    assert GroupDeviceTypePermission.objects.filter(devicetype=dt).count() == 1

    # 3. as staff => success
    server("staff", "staff").scheduler.device_types.perms_delete(
        "dt-01", "group", "change_devicetype"
    )
    assert GroupDeviceTypePermission.objects.filter(devicetype=dt).count() == 0

    # 4. device-type does not exist
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("staff", "staff").scheduler.device_types.perms_delete(
            "dt-02", "group", "change_devicetype"
        )
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Device-type 'dt-02' was not found."

    # 5. group does not exist
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("staff", "staff").scheduler.device_types.perms_delete(
            "dt-01", "group11", "change_devicetype"
        )
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Group 'group11' was not found."


@pytest.mark.django_db
def test_device_types_perms_list(setup):
    dt = DeviceType.objects.create(name="dt-01")

    # 1. as anonymous => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.device_types.perms_list("dt-01")
    assert exc.value.faultCode == 401
    assert (
        exc.value.faultString
        == "Authentication with user and token required for this API."
    )

    # 2. as user => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("user", "user").scheduler.device_types.perms_list("dt-01")
    assert exc.value.faultCode == 403
    assert exc.value.faultString == "forbidden"

    # 3. as staff => success.
    perms = server("staff", "staff").scheduler.device_types.perms_list("dt-01")
    assert perms == []
    GroupDeviceTypePermission.objects.assign_perm(
        "change_devicetype", Group.objects.get(name="group"), dt
    )
    perms = server("staff", "staff").scheduler.device_types.perms_list("dt-01")
    assert len(perms) == 1
    assert perms[0]["name"] == "change_devicetype"
    assert perms[0]["group"] == "group"

    # 4. device-type does not exist
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("staff", "staff").scheduler.device_types.perms_list("dt-02")
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Device-type 'dt-02' was not found."


@pytest.mark.django_db
def test_device_types_show(setup):
    # 1. Device-type does not exist
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.device_types.show("qemu")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "Device-type 'qemu' was not found."  # nosec

    # 2. Normal case
    dt = DeviceType.objects.create(name="qemu")
    data = server("admin", "admin").scheduler.device_types.show("qemu")

    from lava_server.files import File

    assert data == {  # nosec
        "name": "qemu",
        "description": None,
        "display": True,
        "health_disabled": False,
        "health_denominator": "hours",
        "health_frequency": 24,
        "aliases": [],
        "devices": [],
        "default_template": False,
        "permissions": [],
    }

    # 3. More details
    Device.objects.create(hostname="device01", device_type=dt)
    data = server("admin", "admin").scheduler.device_types.show("qemu")

    assert data == {  # nosec
        "name": "qemu",
        "description": None,
        "display": True,
        "health_disabled": False,
        "health_denominator": "hours",
        "health_frequency": 24,
        "aliases": [],
        "devices": ["device01"],
        "default_template": False,
        "permissions": [],
    }

    # 4. Add a group permission.
    group = Group.objects.get(name="group")
    GroupDeviceTypePermission.objects.assign_perm("change_devicetype", group, dt)
    data = server("admin", "admin").scheduler.device_types.show("qemu")
    assert data == {
        "name": "qemu",
        "description": None,
        "display": True,
        "health_disabled": False,
        "health_denominator": "hours",
        "health_frequency": 24,
        "aliases": [],
        "devices": ["device01"],
        "default_template": False,
        "permissions": [
            {"name": "change_devicetype", "group": "group"},
        ],
    }


@pytest.mark.django_db
def test_device_types_update(setup):
    # 1. Device-type does not exist
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.device_types.update(
            "qemu", None, None, None, None, None, None
        )
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "Device-type 'qemu' was not found."  # nosec

    # 2. Normal case
    dt = DeviceType.objects.create(name="qemu")
    server("admin", "admin").scheduler.device_types.update(
        "qemu", None, None, None, None, None, None
    )
    dt = DeviceType.objects.get(name="qemu")
    assert dt.description == None  # nosec

    server("admin", "admin").scheduler.device_types.update(
        "qemu", "emulated", True, None, 12, "jobs", True
    )
    dt = DeviceType.objects.get(name="qemu")
    assert dt.description == "emulated"  # nosec
    assert dt.display is True  # nosec
    assert dt.health_frequency == 12  # nosec
    assert dt.health_denominator == DeviceType.HEALTH_PER_JOB  # nosec

    server("admin", "admin").scheduler.device_types.update(
        "qemu", None, None, None, None, "hours", None
    )
    dt = DeviceType.objects.get(name="qemu")
    assert dt.description == "emulated"  # nosec
    assert dt.display is True  # nosec
    assert dt.health_frequency == 12  # nosec
    assert dt.health_denominator == DeviceType.HEALTH_PER_HOUR  # nosec

    # 3. wrong health denominator
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.device_types.update(
            "qemu", None, None, None, None, "job", None
        )
    assert exc.value.faultCode == 400  # nosec
    assert exc.value.faultString == "Bad request: invalid health_denominator."  # nosec


@pytest.mark.django_db
def test_device_types_aliases_add(setup):
    # 1. Device-type does not exist
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.device_types.aliases.add("qemu", "kvm")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "Device-type 'qemu' was not found."  # nosec

    # 2. Normal case
    dt = DeviceType.objects.create(name="qemu")
    server("admin", "admin").scheduler.device_types.aliases.add("qemu", "kvm")
    assert Alias.objects.count() == 1  # nosec
    assert Alias.objects.all()[0].name == "kvm"  # nosec
    assert DeviceType.objects.get(name="qemu").aliases.count() == 1  # nosec
    assert DeviceType.objects.get(name="qemu").aliases.all()[0].name == "kvm"  # nosec


@pytest.mark.django_db
def test_device_types_aliases_list(setup):
    # 1. Device-type does not exist
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.device_types.aliases.list("qemu")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "Device-type 'qemu' was not found."  # nosec

    # 2. Normal case
    dt = DeviceType.objects.create(name="qemu")
    data = server("admin", "admin").scheduler.device_types.aliases.list("qemu")
    assert data == []  # nosec

    dt.aliases.add(Alias.objects.create(name="kvm"))
    data = server("admin", "admin").scheduler.device_types.aliases.list("qemu")
    assert data == ["kvm"]  # nosec


@pytest.mark.django_db
def test_device_types_aliases_delete(setup):
    # 1. Device-type does not exist
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.device_types.aliases.delete("qemu", "kvm")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "Device-type 'qemu' was not found."  # nosec

    # 2. Alias does not exist
    dt = DeviceType.objects.create(name="qemu")
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.device_types.aliases.delete("qemu", "kvm")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "Alias 'kvm' was not found."  # nosec

    # 3. Normal case
    dt.aliases.add(Alias.objects.create(name="kvm"))
    server("admin", "admin").scheduler.device_types.aliases.delete("qemu", "kvm")
    assert Alias.objects.count() == 1  # nosec
    assert Alias.objects.all()[0].name == "kvm"  # nosec
    assert DeviceType.objects.get(name="qemu").aliases.count() == 0  # nosec


@pytest.mark.django_db
def test_tags_add(setup):
    # 1. as anonymous => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.tags.add("hdd")
    assert exc.value.faultCode == 401  # nosec
    assert (  # nosec
        exc.value.faultString
        == "Authentication with user and token required for this API."
    )
    assert Tag.objects.count() == 0  # nosec

    # 2. as user => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("user", "user").scheduler.tags.add("hdd")
    assert exc.value.faultCode == 403  # nosec
    assert (  # nosec
        exc.value.faultString
        == "User 'user' is missing permission lava_scheduler_app.add_tag."
    )
    assert Tag.objects.count() == 0  # nosec

    # 3. as admin => success
    assert server("admin", "admin").scheduler.tags.add("hdd") is None  # nosec
    assert Tag.objects.count() == 1  # nosec
    assert Tag.objects.all()[0].name == "hdd"  # nosec
    assert Tag.objects.all()[0].description is None  # nosec

    # 4. as admin set description => success
    assert (  # nosec
        server("admin", "admin").scheduler.tags.add("audio", "audio capture") is None
    )
    assert Tag.objects.count() == 2  # nosec
    assert Tag.objects.all()[1].name == "audio"  # nosec
    assert Tag.objects.all()[1].description == "audio capture"  # nosec

    # 5. already used name => exception
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.tags.add("hdd")
    assert exc.value.faultCode == 400  # nosec
    assert exc.value.faultString == "Bad request: tag already exists?"  # nosec


@pytest.mark.django_db
def test_tags_delete(setup):
    Tag.objects.create(name="hdd")
    Tag.objects.create(name="audio", description="audio capture")

    server("admin", "admin").scheduler.tags.delete("hdd")
    assert Tag.objects.count() == 1  # nosec
    assert Tag.objects.all()[0].name == "audio"  # nosec

    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.tags.delete("hdd")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "Tag 'hdd' was not found."  # nosec

    server("admin", "admin").scheduler.tags.delete("audio")
    assert Tag.objects.count() == 0  # nosec


@pytest.mark.django_db
def test_tags_show(setup):
    tag1 = Tag.objects.create(name="hdd")
    tag2 = Tag.objects.create(name="audio", description="audio capture")

    data = server().scheduler.tags.show("hdd")
    assert data == {"name": "hdd", "description": None, "devices": []}  # nosec

    # Create some devices
    dt = DeviceType.objects.create(name="dt-01")
    device = Device.objects.create(hostname="d-01", device_type=dt)
    device.tags.add(tag1)

    data = server().scheduler.tags.show("hdd")
    assert data == {"name": "hdd", "description": None, "devices": ["d-01"]}  # nosec

    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.tags.show("ssd")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "Tag 'ssd' was not found."  # nosec


@pytest.mark.django_db
def test_tags_list(setup):
    data = server().scheduler.tags.list()
    assert data == []  # nosec

    Tag.objects.create(name="hdd")
    data = server().scheduler.tags.list()
    assert data == [{"name": "hdd", "description": None}]  # nosec

    Tag.objects.create(name="audio", description="audio capture")
    data = server().scheduler.tags.list()
    assert data == [  # nosec
        {"name": "audio", "description": "audio capture"},
        {"name": "hdd", "description": None},
    ]


@pytest.mark.django_db
def test_workers_add(setup):
    # 1. as anonymous => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.workers.add("dispatcher.example.com")
    assert exc.value.faultCode == 401  # nosec
    assert (  # nosec
        exc.value.faultString
        == "Authentication with user and token required for this API."
    )
    assert (  # nosec
        Worker.objects.count() == 1
    )  # "example.com" is part of the migrations

    # 2. as user => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("user", "user").scheduler.workers.add("dispatcher.example.com")
    assert exc.value.faultCode == 403  # nosec
    assert (  # nosec
        exc.value.faultString
        == "User 'user' is missing permission lava_scheduler_app.add_worker."
    )
    assert (  # nosec
        Worker.objects.count() == 1
    )  # "example.com" is part of the migrations

    # 3. as admin => success
    assert (  # nosec
        server("admin", "admin").scheduler.workers.add("dispatcher.example.com") is None
    )
    assert Worker.objects.count() == 2  # nosec
    worker = Worker.objects.get(hostname="dispatcher.example.com")
    assert worker.description is None  # nosec
    assert worker.health == Worker.HEALTH_ACTIVE  # nosec

    # 4. as admin set description and health => success
    assert (  # nosec
        server("admin", "admin").scheduler.workers.add(
            "worker.example.com", "worker", True
        )
        is None
    )
    assert Worker.objects.count() == 3  # nosec
    worker = Worker.objects.get(hostname="worker.example.com")
    assert worker.description == "worker"  # nosec
    assert worker.health == Worker.HEALTH_RETIRED  # nosec

    # 5. already used hostname => exception
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.add("dispatcher.example.com")
    assert exc.value.faultCode == 400  # nosec
    assert exc.value.faultString == "Bad request: worker already exists?"  # nosec


def test_workers_delete(setup):
    # 1. as anonymous => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        # "example.com" is part of the migrations
        server().scheduler.workers.delete("example.com")
    assert exc.value.faultCode == 401
    assert (
        exc.value.faultString
        == "Authentication with user and token required for this API."
    )
    assert Worker.objects.count() == 1

    # 2. as user => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("user", "user").scheduler.workers.delete("example.com")
    assert exc.value.faultCode == 403
    assert (
        exc.value.faultString
        == "User 'user' is missing permission lava_scheduler_app.delete_worker."
    )
    assert Worker.objects.count() == 1

    # 3. as admin => success
    assert server("admin", "admin").scheduler.workers.delete("example.com") is None
    assert Worker.objects.count() == 0

    # 4. worker does not exists => 404
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.delete("example.com")
    assert exc.value.faultCode == 404
    assert exc.value.faultString == "Worker 'example.com' was not found."


@pytest.mark.django_db
def test_workers_get_config_old_config(setup, mocker, tmp_path):
    (tmp_path / "example.com.yaml").write_text("hello", encoding="utf-8")
    mocker.patch(
        "lava_server.files.File.KINDS",
        {
            "dispatcher": [
                str(tmp_path / "{name}/dispatcher.yaml"),
                str(tmp_path / "{name}.yaml"),
            ]
        },
    )

    assert (  # nosec
        str(server("admin", "admin").scheduler.workers.get_config("example.com"))
        == "hello"
    )


@pytest.mark.django_db
def test_workers_get_config_new_config(setup, mocker, tmp_path):
    (tmp_path / "example.com").mkdir()
    (tmp_path / "example.com" / "dispatcher.yaml").write_text(
        "hello world", encoding="utf-8"
    )
    mocker.patch(
        "lava_server.files.File.KINDS",
        {
            "dispatcher": [
                str(tmp_path / "{name}/dispatcher.yaml"),
                str(tmp_path / "{name}.yaml"),
            ]
        },
    )

    assert (  # nosec
        str(server("admin", "admin").scheduler.workers.get_config("example.com"))
        == "hello world"
    )


@pytest.mark.django_db
def test_workers_get_config_exceptions(setup, mocker, tmp_path):
    mocker.patch(
        "lava_server.files.File.KINDS",
        {
            "dispatcher": [
                str(tmp_path / "{name}/dispatcher.yaml"),
                str(tmp_path / "{name}.yaml"),
            ]
        },
    )

    # 1. invalid worker name (should not be a path)
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.get_config("example.com/../")
    assert exc.value.faultCode == 400  # nosec
    assert exc.value.faultString == "Invalid worker name"  # nosec

    # 2. worker does not exists
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.get_config("worker.example.com")
    assert exc.value.faultCode == 404  # nosec
    assert (  # nosec
        exc.value.faultString == "Worker 'worker.example.com' was not found."
    )

    # 3. no configuration file
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.get_config("example.com")
    assert exc.value.faultCode == 404  # nosec
    assert (  # nosec
        exc.value.faultString
        == "Worker 'example.com' does not have a dispatcher configuration"
    )


@pytest.mark.django_db
def test_workers_get_env_old_config(setup, mocker, tmp_path):
    (tmp_path / "env.yaml").write_text("hello", encoding="utf-8")
    mocker.patch(
        "lava_server.files.File.KINDS",
        {"env": [str(tmp_path / "{name}/env.yaml"), str(tmp_path / "env.yaml")]},
    )

    assert (  # nosec
        str(server("admin", "admin").scheduler.workers.get_env("example.com"))
        == "hello"
    )


@pytest.mark.django_db
def test_workers_get_env_new_config(setup, mocker, tmp_path):
    (tmp_path / "example.com").mkdir()
    (tmp_path / "example.com" / "env.yaml").write_text("hello world", encoding="utf-8")
    mocker.patch(
        "lava_server.files.File.KINDS",
        {"env": [str(tmp_path / "{name}/env.yaml"), str(tmp_path / "env.yaml")]},
    )

    assert (  # nosec
        str(server("admin", "admin").scheduler.workers.get_env("example.com"))
        == "hello world"
    )


@pytest.mark.django_db
def test_workers_get_env_exceptions(setup, mocker, tmp_path):
    mocker.patch(
        "lava_server.files.File.KINDS",
        {"env": [str(tmp_path / "{name}/env.yaml"), str(tmp_path / "env.yaml")]},
    )

    # 1. invalid worker name (should not be a path)
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.get_env("example.com/../")
    assert exc.value.faultCode == 400  # nosec
    assert exc.value.faultString == "Invalid worker name"  # nosec

    # 2. worker does not exists
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.get_env("worker.example.com")
    assert exc.value.faultCode == 404  # nosec
    assert (  # nosec
        exc.value.faultString == "Worker 'worker.example.com' was not found."
    )

    # 3. no configuration file
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.get_env("example.com")
    assert exc.value.faultCode == 404  # nosec
    assert (  # nosec
        exc.value.faultString == "Worker 'example.com' does not have an env file"
    )


@pytest.mark.django_db
def test_workers_get_env_dut_old_config(setup, mocker, tmp_path):
    (tmp_path / "env-dut.yaml").write_text("hello", encoding="utf-8")
    mocker.patch(
        "lava_server.files.File.KINDS",
        {
            "env-dut": [
                str(tmp_path / "{name}/env-dut.yaml"),
                str(tmp_path / "env-dut.yaml"),
            ]
        },
    )

    assert (  # nosec
        str(server("admin", "admin").scheduler.workers.get_env_dut("example.com"))
        == "hello"
    )


@pytest.mark.django_db
def test_workers_get_env_dut_new_config(setup, mocker, tmp_path):
    (tmp_path / "example.com").mkdir()
    (tmp_path / "example.com" / "env-dut.yaml").write_text(
        "hello world", encoding="utf-8"
    )
    mocker.patch(
        "lava_server.files.File.KINDS",
        {
            "env-dut": [
                str(tmp_path / "{name}/env-dut.yaml"),
                str(tmp_path / "env-dut.yaml"),
            ]
        },
    )

    assert (  # nosec
        str(server("admin", "admin").scheduler.workers.get_env_dut("example.com"))
        == "hello world"
    )


@pytest.mark.django_db
def test_workers_get_env_dut_exceptions(setup, mocker, tmp_path):
    mocker.patch(
        "lava_server.files.File.KINDS",
        {
            "env-dut": [
                str(tmp_path / "{name}/env-dut.yaml"),
                str(tmp_path / "env-dut.yaml"),
            ]
        },
    )

    # 1. invalid worker name (should not be a path)
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.get_env_dut("example.com/../")
    assert exc.value.faultCode == 400  # nosec
    assert exc.value.faultString == "Invalid worker name"  # nosec

    # 2. worker does not exists
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.get_env_dut("worker.example.com")
    assert exc.value.faultCode == 404  # nosec
    assert (  # nosec
        exc.value.faultString == "Worker 'worker.example.com' was not found."
    )

    # 3. no configuration file
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.get_env_dut("example.com")
    assert exc.value.faultCode == 404  # nosec
    assert (  # nosec
        exc.value.faultString == "Worker 'example.com' does not have an env-dut file"
    )


@pytest.mark.django_db
def test_workers_set_config(setup, mocker, tmp_path):
    mocker.patch(
        "lava_server.files.File.KINDS",
        {
            "dispatcher": [
                str(tmp_path / "{name}/dispatcher.yaml"),
                str(tmp_path / "{name}.yaml"),
            ]
        },
    )

    assert (  # nosec
        server("admin", "admin").scheduler.workers.set_config("example.com", "hello")
        is True
    )
    assert (tmp_path / "example.com" / "dispatcher.yaml").read_text(  # nosec
        encoding="utf-8"
    ) == "hello"


@pytest.mark.django_db
def test_workers_set_config_exceptions(setup, mocker, tmp_path):
    mocker.patch(
        "lava_server.files.File.KINDS",
        {
            "dispatcher": [
                str(tmp_path / "{name}/dispatcher.yaml"),
                str(tmp_path / "{name}.yaml"),
            ]
        },
    )

    # 1. invalid worker name (should not be a path)
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.set_config(
            "example.com/../", "error"
        )
    assert exc.value.faultCode == 400  # nosec
    assert exc.value.faultString == "Invalid worker name"  # nosec

    # 2. worker does not exists
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.set_config(
            "worker.example.com", "error"
        )
    assert exc.value.faultCode == 404  # nosec
    assert (  # nosec
        exc.value.faultString == "Worker 'worker.example.com' was not found."
    )
    # 3. as user => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("user", "user").scheduler.workers.set_config(
            "worker.example.com", "error"
        )
    assert exc.value.faultCode == 403  # nosec
    assert (  # nosec
        exc.value.faultString
        == "User 'user' is missing permission lava_scheduler_app.change_worker."
    )


@pytest.mark.django_db
def test_workers_set_env(setup, mocker, tmp_path):
    mocker.patch(
        "lava_server.files.File.KINDS",
        {"env": [str(tmp_path / "{name}/env.yaml"), str(tmp_path / "env.yaml")]},
    )

    assert (  # nosec
        server("admin", "admin").scheduler.workers.set_env("example.com", "hello")
        is True
    )
    assert (tmp_path / "example.com" / "env.yaml").read_text(  # nosec
        encoding="utf-8"
    ) == "hello"


@pytest.mark.django_db
def test_workers_set_env_exceptions(setup, mocker, tmp_path):
    mocker.patch(
        "lava_server.files.File.KINDS",
        {"env": [str(tmp_path / "{name}/env.yaml"), str(tmp_path / "env.yaml")]},
    )

    # 1. invalid worker name (should not be a path)
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.set_env("example.com/../", "error")
    assert exc.value.faultCode == 400  # nosec
    assert exc.value.faultString == "Invalid worker name"  # nosec

    # 2. worker does not exists
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.set_env(
            "worker.example.com", "error"
        )
    assert exc.value.faultCode == 404  # nosec
    assert (  # nosec
        exc.value.faultString == "Worker 'worker.example.com' was not found."
    )
    # 3. as user => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("user", "user").scheduler.workers.set_env("worker.example.com", "error")
    assert exc.value.faultCode == 403  # nosec
    assert (  # nosec
        exc.value.faultString
        == "User 'user' is missing permission lava_scheduler_app.change_worker."
    )


@pytest.mark.django_db
def test_workers_set_env_dut(setup, mocker, tmp_path):
    mocker.patch(
        "lava_server.files.File.KINDS",
        {
            "env-dut": [
                str(tmp_path / "{name}/env-dut.yaml"),
                str(tmp_path / "env-dut.yaml"),
            ]
        },
    )

    assert (  # nosec
        server("admin", "admin").scheduler.workers.set_env_dut("example.com", "hello")
        is True
    )
    assert (tmp_path / "example.com" / "env-dut.yaml").read_text(  # nosec
        encoding="utf-8"
    ) == "hello"


@pytest.mark.django_db
def test_workers_set_env_dut_exceptions(setup, mocker, tmp_path):
    mocker.patch(
        "lava_server.files.File.KINDS",
        {
            "env-dut": [
                str(tmp_path / "{name}/env-dut.yaml"),
                str(tmp_path / "env-dut.yaml"),
            ]
        },
    )

    # 1. invalid worker name (should not be a path)
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.set_env_dut(
            "example.com/../", "error"
        )
    assert exc.value.faultCode == 400  # nosec
    assert exc.value.faultString == "Invalid worker name"  # nosec

    # 2. worker does not exists
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.set_env_dut(
            "worker.example.com", "error"
        )
    assert exc.value.faultCode == 404  # nosec
    assert (  # nosec
        exc.value.faultString == "Worker 'worker.example.com' was not found."
    )
    # 3. as user => error
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("user", "user").scheduler.workers.set_env_dut(
            "worker.example.com", "error"
        )
    assert exc.value.faultCode == 403  # nosec
    assert (  # nosec
        exc.value.faultString
        == "User 'user' is missing permission lava_scheduler_app.change_worker."
    )


@pytest.mark.django_db
def test_workers_list(setup):
    data = server().scheduler.workers.list()
    assert data == ["example.com"]  # nosec

    Worker.objects.create(hostname="worker01")
    data = server().scheduler.workers.list()
    assert data == ["example.com", "worker01"]  # nosec

    Worker.objects.create(hostname="worker02")
    server("admin", "admin").scheduler.workers.update("worker02", None, "RETIRED")
    data = server().scheduler.workers.list()
    assert data == ["example.com", "worker01"]  # nosec

    data = server().scheduler.workers.list(True)
    assert data == ["example.com", "worker01", "worker02"]  # nosec


@pytest.mark.django_db
def test_workers_show(setup):
    data = server().scheduler.workers.show("example.com")
    assert set(data.keys()) == {  # nosec
        "hostname",
        "description",
        "state",
        "health",
        "devices",
        "last_ping",
        "job_limit",
        "version",
        "default_config",
        "default_env",
        "default_env_dut",
    }
    assert data["hostname"] == "example.com"  # nosec
    assert data["job_limit"] == 0  # nosec

    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.workers.show("bla")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "Worker 'bla' was not found."  # nosec


@pytest.mark.django_db
def test_workers_update(setup):
    # 1. as anonymous => failure
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server().scheduler.workers.update("example.com")
    assert exc.value.faultCode == 401  # nosec
    assert (  # nosec
        exc.value.faultString
        == "Authentication with user and token required for this API."
    )

    # 2. as user => failure
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("user", "user").scheduler.workers.update("example.com")
    assert exc.value.faultCode == 403  # nosec
    assert (  # nosec
        exc.value.faultString
        == "User 'user' is missing permission lava_scheduler_app.change_worker."
    )

    # 3. as admin
    assert (  # nosec
        server("admin", "admin").scheduler.workers.update("example.com") is None
    )
    assert Worker.objects.get(hostname="example.com").description is None  # nosec
    assert (  # nosec
        Worker.objects.get(hostname="example.com").health == Worker.HEALTH_ACTIVE
    )

    assert (  # nosec
        server("admin", "admin").scheduler.workers.update("example.com", "dummy worker")
        is None
    )
    assert (  # nosec
        Worker.objects.get(hostname="example.com").description == "dummy worker"
    )
    assert (  # nosec
        Worker.objects.get(hostname="example.com").health == Worker.HEALTH_ACTIVE
    )

    assert (  # nosec
        server("admin", "admin").scheduler.workers.update(
            "example.com", None, "MAINTENANCE"
        )
        is None
    )
    assert (  # nosec
        Worker.objects.get(hostname="example.com").description == "dummy worker"
    )
    assert (  # nosec
        Worker.objects.get(hostname="example.com").health == Worker.HEALTH_MAINTENANCE
    )
    assert (  # nosec
        server("admin", "admin").scheduler.workers.update(
            "example.com", None, "RETIRED"
        )
        is None
    )
    assert (  # nosec
        Worker.objects.get(hostname="example.com").health == Worker.HEALTH_RETIRED
    )
    assert (  # nosec
        server("admin", "admin").scheduler.workers.update("example.com", None, "ACTIVE")
        is None
    )
    assert (  # nosec
        Worker.objects.get(hostname="example.com").health == Worker.HEALTH_ACTIVE
    )

    # worker does not exists
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.update("something")
    assert exc.value.faultCode == 404  # nosec
    assert exc.value.faultString == "Worker 'something' was not found."  # nosec

    # invalid health
    with pytest.raises(xmlrpc.client.Fault) as exc:
        server("admin", "admin").scheduler.workers.update("example.com", None, "wrong")
    assert exc.value.faultCode == 400  # nosec
    assert exc.value.faultString == "Invalid health: wrong"  # nosec
