import yaml
from django.contrib.auth.models import Group, Permission, User
from django.db.models import Q
from django.test import TestCase
from jinja2.exceptions import TemplateNotFound as JinjaTemplateNotFound
from jinja2.sandbox import SandboxedEnvironment as JinjaSandboxEnv

from lava_common.yaml import yaml_safe_load
from lava_scheduler_app.dbutils import (
    active_device_types,
    invalid_template,
    load_devicetype_template,
)
from lava_scheduler_app.models import (
    Device,
    DeviceType,
    GroupDevicePermission,
    GroupDeviceTypePermission,
)
from lava_server.files import File

# python3 needs print to be a function, so disable pylint


class ModelFactory:
    def __init__(self):
        self._int = 0

    def getUniqueInteger(self):
        self._int += 1
        return self._int

    def getUniqueString(self, prefix="generic"):
        return "%s-%d" % (prefix, self.getUniqueInteger())

    def get_unique_user(self, prefix="generic"):
        return "%s-%d" % (prefix, User.objects.count() + 1)

    def get_unique_group(self, prefix="group"):
        return "%s-%d" % (prefix, Group.objects.count() + 1)

    def make_user(self):
        return User.objects.create_user(
            self.get_unique_user(),
            "%s@mail.invalid" % (self.getUniqueString(),),
            self.getUniqueString(),
        )

    def make_group(self):
        return Group.objects.create(name=self.get_unique_group())


class TestCaseWithFactory(TestCase):
    def setUp(self):
        TestCase.setUp(self)
        self.factory = ModelFactory()


class DeviceTest(TestCaseWithFactory):
    def test_device_permissions_test(self):
        dt = DeviceType(name="type1")
        dt.save()
        device = Device(device_type=dt, hostname="device1")
        device.save()

        group = self.factory.make_group()
        user1 = self.factory.make_user()
        user1.groups.add(group)

        group2 = self.factory.make_group()
        user2 = self.factory.make_user()
        user2.groups.add(group2)

        GroupDevicePermission.objects.assign_perm("submit_to_device", group, device)
        self.assertEqual(device.can_submit(user2), False)
        self.assertEqual(device.can_submit(user1), True)
        GroupDevicePermission.objects.remove_perm("submit_to_device", group, device)
        delattr(user1, "_cached_has_perm")
        delattr(user2, "_cached_has_perm")

        self.assertEqual(device.can_view(user2), True)
        self.assertEqual(device.can_view(user1), True)

        GroupDeviceTypePermission.objects.assign_perm("view_devicetype", group, dt)
        delattr(user1, "_cached_has_perm")
        delattr(user2, "_cached_has_perm")
        self.assertEqual(device.can_view(user2), False)
        self.assertEqual(device.can_view(user1), True)

        GroupDeviceTypePermission.objects.remove_perm("view_devicetype", group, dt)
        GroupDevicePermission.objects.assign_perm("view_device", group, device)
        delattr(user1, "_cached_has_perm")
        delattr(user2, "_cached_has_perm")
        self.assertEqual(device.can_view(user2), False)
        self.assertEqual(device.can_view(user1), True)

        GroupDevicePermission.objects.assign_perm("view_device", group2, device)
        delattr(user1, "_cached_has_perm")
        delattr(user2, "_cached_has_perm")
        self.assertEqual(device.can_view(user2), True)
        self.assertEqual(device.can_view(user1), True)

        device.health = Device.HEALTH_RETIRED
        device.save()
        self.assertEqual(device.can_submit(user2), False)
        self.assertEqual(device.can_submit(user1), False)

        # Test that global permission works as intended.
        user3 = self.factory.make_user()
        user3.user_permissions.add(Permission.objects.get(codename="change_device"))
        self.assertEqual(device.can_change(user3), True)


class DeviceTypeTest(TestCaseWithFactory):
    def tearDown(self):
        super().tearDown()
        Device.objects.all().delete()
        DeviceType.objects.all().delete()

    """
    Test loading of device-type information
    """

    def test_device_type_parser(self):
        data = load_devicetype_template("beaglebone-black")
        self.assertIsNotNone(data)
        self.assertIn("actions", data)
        self.assertIn("deploy", data["actions"])
        self.assertIn("boot", data["actions"])

    def test_device_type_templates(self):
        """
        Ensure each template renders valid YAML
        """
        env = JinjaSandboxEnv(
            loader=File("device-type").loader(), trim_blocks=True, autoescape=False
        )

        for template_name in File("device-type").list("*.jinja2"):
            try:
                template = env.get_template(template_name)
            except JinjaTemplateNotFound as exc:
                self.fail("%s: %s" % (template_name, exc))
            data = None
            try:
                data = template.render()
                yaml_data = yaml_safe_load(data)
            except yaml.YAMLError as exc:
                print(data)  # for easier debugging - use the online yaml parser
                self.fail("%s: %s" % (template_name, exc))
            self.assertIsInstance(yaml_data, dict)

    def test_retired_invalid_template(self):
        name = "beaglebone-black"
        dt = DeviceType(name=name)
        dt.save()
        dt.refresh_from_db()
        device = Device(device_type=dt, hostname="bbb-01", health=Device.HEALTH_RETIRED)
        device.save()
        device.refresh_from_db()
        self.assertEqual(
            [],
            list(
                Device.objects.filter(
                    Q(device_type=dt), ~Q(health=Device.HEALTH_RETIRED)
                )
            ),
        )
        self.assertIsNotNone([d for d in Device.objects.filter(device_type=dt)])
        self.assertFalse(invalid_template(device.device_type))

    def test_bbb_valid_template(self):
        name = "beaglebone-black"
        dt = DeviceType(name=name)
        dt.save()
        dt.refresh_from_db()
        device = Device(device_type=dt, hostname="bbb-01", health=Device.HEALTH_GOOD)
        device.save()
        device.refresh_from_db()
        self.assertIsNotNone([d for d in Device.objects.filter(device_type=dt)])
        self.assertTrue(File("device-type", name).exists())
        self.assertIsNotNone([device in Device.objects.filter(device_type=dt)])
        self.assertIsNotNone(device.load_configuration())
        self.assertTrue(bool(load_devicetype_template(device.device_type.name)))
        self.assertFalse(invalid_template(device.device_type))

    def test_unknown_invalid_template(self):
        name = "nowhere-never-skip"
        dt = DeviceType(name=name)
        dt.save()
        dt.refresh_from_db()
        device = Device(device_type=dt, hostname="test-01", health=Device.HEALTH_GOOD)
        device.save()
        device.refresh_from_db()
        self.assertIsNotNone([d for d in Device.objects.filter(device_type=dt)])
        self.assertIsNone(device.load_configuration())
        self.assertIsNotNone([device in Device.objects.filter(device_type=dt)])
        self.assertFalse(bool(load_devicetype_template(device.device_type.name)))
        self.assertTrue(invalid_template(device.device_type))

    def test_juno_vexpress_valid_template(self):
        name = "juno-r2"
        dt = DeviceType(name=name)
        dt.save()
        dt.refresh_from_db()
        device = Device(
            device_type=dt, hostname="juno-r2-01", health=Device.HEALTH_GOOD
        )
        device.save()
        device.refresh_from_db()
        self.assertIsNotNone([d for d in Device.objects.filter(device_type=dt)])
        self.assertFalse(File("device-type", "juno-r2").exists())
        self.assertEqual("juno-r2-01", device.hostname)
        self.assertIsNotNone(device.load_configuration())
        self.assertEqual(
            [device], [device for device in Device.objects.filter(device_type=dt)]
        )
        self.assertEqual("juno", device.get_extends())
        self.assertFalse(bool(load_devicetype_template(device.device_type.name)))
        self.assertFalse(invalid_template(device.device_type))

    def test_active_device_types(self):
        name = "beaglebone-black"
        dt = DeviceType(name=name)
        dt.save()
        dt.refresh_from_db()
        device = Device(device_type=dt, hostname="bbb-01", health=Device.HEALTH_GOOD)
        device.save()
        device = Device(device_type=dt, hostname="bbb-02", health=Device.HEALTH_RETIRED)
        device.save()

        name = "juno-r2"
        dt = DeviceType(name=name)
        dt.save()
        dt.refresh_from_db()
        device = Device(
            device_type=dt, hostname="juno-r2-01", health=Device.HEALTH_RETIRED
        )
        device.save()

        name = "juno"
        dt = DeviceType(name=name)
        dt.display = False
        dt.save()
        dt.refresh_from_db()
        dt.refresh_from_db()
        device = Device(
            device_type=dt, hostname="juno-01", health=Device.HEALTH_UNKNOWN
        )
        device.save()

        name = "qemu"
        dt = DeviceType(name=name)
        dt.save()
        dt.refresh_from_db()
        device = Device(device_type=dt, hostname="qemu-01", health=Device.HEALTH_GOOD)
        device.save()

        self.assertEqual(
            {"bbb-01", "bbb-02", "juno-r2-01", "qemu-01", "juno-01"},
            set(Device.objects.all().values_list("hostname", flat=True)),
        )

        self.assertEqual(
            {"beaglebone-black", "juno", "juno-r2", "qemu"},
            set(DeviceType.objects.values_list("name", flat=True)),
        )

        # exclude juno-r2 because all devices of that device-type are retired.
        # exclude juno because the device_type is set to not be displayed.
        # include beaglebone-black because not all devices of that type are retired.
        # include qemu because none of the devices of that type are retired.
        self.assertEqual(
            {"beaglebone-black", "qemu"},
            set(active_device_types().values_list("name", flat=True)),
        )
