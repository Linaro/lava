# Copyright (C) 2019 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
import tempfile
from pathlib import Path

from django.contrib.auth.models import Group, Permission, User
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.test import TestCase, override_settings

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
            f"{self.getUniqueString()}@mail.invalid",
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

    def test_device_invalid_name(self):
        dt = DeviceType.objects.create(name="type1")
        with self.assertRaises(ValidationError):
            Device.objects.create(device_type=dt, hostname="device1/")
        dev = Device(device_type=dt, hostname="device2/")
        with self.assertRaises(ValidationError):
            dev.save()


class DeviceTypeTest(TestCaseWithFactory):
    """
    Test loading of device-type information
    """

    def test_device_type_parser(self):
        data = load_devicetype_template("beaglebone-black")
        self.assertIsNotNone(data)
        self.assertIn("actions", data)
        self.assertIn("deploy", data["actions"])
        self.assertIn("boot", data["actions"])

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
        self.assertIsNotNone(list(Device.objects.filter(device_type=dt)))
        self.assertFalse(invalid_template(device.device_type))

    def test_bbb_valid_template(self):
        name = "beaglebone-black"
        dt = DeviceType(name=name)
        dt.save()
        dt.refresh_from_db()
        device = Device(device_type=dt, hostname="bbb-01", health=Device.HEALTH_GOOD)
        device.save()
        device.refresh_from_db()
        self.assertIsNotNone(list(Device.objects.filter(device_type=dt)))
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
        self.assertIsNotNone(list(Device.objects.filter(device_type=dt)))
        self.assertIsNone(device.load_configuration())
        self.assertIsNotNone([device in Device.objects.filter(device_type=dt)])
        self.assertFalse(bool(load_devicetype_template(device.device_type.name)))
        self.assertTrue(invalid_template(device.device_type))

    def test_juno_vexpress_valid_template(self):
        name = "juno"
        dt = DeviceType(name=name)
        dt.save()
        dt.refresh_from_db()
        device = Device(device_type=dt, hostname="juno-01", health=Device.HEALTH_GOOD)
        device.save()
        device.refresh_from_db()
        self.assertIsNotNone(list(Device.objects.filter(device_type=dt)))
        self.assertTrue(File("device-type", "juno").exists())
        self.assertEqual("juno-01", device.hostname)
        self.assertIsNotNone(device.load_configuration())
        self.assertEqual([device], list(Device.objects.filter(device_type=dt)))
        self.assertEqual("juno", device.get_extends())
        self.assertTrue(bool(load_devicetype_template(device.device_type.name)))
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

        name = "x15"
        dt = DeviceType(name=name)
        dt.save()
        dt.refresh_from_db()
        device = Device(device_type=dt, hostname="x15-01", health=Device.HEALTH_RETIRED)
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
            {"bbb-01", "bbb-02", "x15-01", "qemu-01", "juno-01"},
            set(Device.objects.all().values_list("hostname", flat=True)),
        )

        self.assertEqual(
            {"beaglebone-black", "juno", "x15", "qemu"},
            set(DeviceType.objects.values_list("name", flat=True)),
        )

        # exclude x15 because all devices of that device-type are retired.
        # exclude juno because the device_type is set to not be displayed.
        # include beaglebone-black because not all devices of that type are retired.
        # include qemu because none of the devices of that type are retired.
        self.assertEqual(
            {"beaglebone-black", "qemu"},
            set(active_device_types().values_list("name", flat=True)),
        )

    def test_devicetype_invalid_name(self):
        with self.assertRaises(ValidationError):
            DeviceType.objects.create(name="type1/")
        dt = DeviceType(name="typ/e2")
        with self.assertRaises(ValidationError):
            dt.save()


class DeviceHealthCheckTest(TestCaseWithFactory):
    """
    Test the lookup of the health check definition
    """

    def test_health_check_falls_back_to_the_device_type_name(self):
        dt = DeviceType.objects.create(name="bcm2711-rpi-4-b")
        device = Device.objects.create(
            device_type=dt, hostname="rpi4-01", health=Device.HEALTH_GOOD
        )
        self.assertEqual("base-uboot", device.get_extends())
        self.assertFalse(File("health-check", "base-uboot").exists())

        health_check = device.get_health_check()
        self.assertIsNotNone(health_check)
        self.assertIn("job_name: rpi4-health-check", health_check)

    def test_health_check_prefers_the_device_type_name(self):
        """The device-type name wins even when the extended template also has a
        health check, so that a check written by `lavacli device-types
        health-check set` is always the one that runs."""
        dt = DeviceType.objects.create(name="bcm2711-rpi-4-b")
        device = Device.objects.create(
            device_type=dt, hostname="juno-01", health=Device.HEALTH_GOOD
        )
        self.assertEqual("juno", device.get_extends())
        self.assertTrue(File("health-check", "juno").exists())

        self.assertIn("job_name: rpi4-health-check", device.get_health_check())

    def rpi4(self):
        dt = DeviceType.objects.create(name="bcm2711-rpi-4-b")
        return Device.objects.create(
            device_type=dt, hostname="rpi4-01", health=Device.HEALTH_GOOD
        )

    def test_health_check_candidate_precedence(self):
        """The full precedence table: the four candidates are tried in order,
        device-type name before template name, .yaml before .yml within each."""
        device = self.rpi4()
        self.assertEqual("base-uboot", device.get_extends())

        cases = [
            (["base-uboot.yaml"], "base-uboot.yaml"),
            (["base-uboot.yml"], "base-uboot.yml"),
            (["bcm2711-rpi-4-b.yaml"], "bcm2711-rpi-4-b.yaml"),
            (["bcm2711-rpi-4-b.yml"], "bcm2711-rpi-4-b.yml"),
            (["base-uboot.yaml", "base-uboot.yml"], "base-uboot.yaml"),
            (["bcm2711-rpi-4-b.yaml", "bcm2711-rpi-4-b.yml"], "bcm2711-rpi-4-b.yaml"),
            (["base-uboot.yaml", "bcm2711-rpi-4-b.yaml"], "bcm2711-rpi-4-b.yaml"),
            (["base-uboot.yml", "bcm2711-rpi-4-b.yaml"], "bcm2711-rpi-4-b.yaml"),
        ]
        for present, expected in cases:
            with self.subTest(present=present):
                with tempfile.TemporaryDirectory() as health_checks:
                    for name in present:
                        Path(health_checks, name).write_text(f"job_name: {name}\n")
                    with override_settings(HEALTH_CHECKS_PATH=health_checks):
                        self.assertEqual(
                            f"job_name: {expected}\n", device.get_health_check()
                        )

    def test_health_check_is_none_when_no_candidate_exists(self):
        device = self.rpi4()
        with tempfile.TemporaryDirectory() as health_checks:
            with override_settings(HEALTH_CHECKS_PATH=health_checks):
                self.assertIsNone(device.get_health_check())

    def test_health_check_skips_an_unreadable_candidate(self):
        """An OSError on a candidate falls through to the next one rather than
        giving up, which is a deliberate change from looking only at existence."""
        device = self.rpi4()
        with tempfile.TemporaryDirectory() as health_checks:
            Path(health_checks, "bcm2711-rpi-4-b.yaml").mkdir()
            Path(health_checks, "base-uboot.yaml").write_text(
                "job_name: from-template\n"
            )
            with override_settings(HEALTH_CHECKS_PATH=health_checks):
                self.assertEqual("job_name: from-template\n", device.get_health_check())

    def test_health_check_order_is_moot_for_the_usual_convention(self):
        """A dictionary extending its own device-type template yields the same
        name twice, so candidate ordering cannot matter for it."""
        DeviceType.objects.create(name="juno")
        device = Device.objects.create(
            device_type=DeviceType.objects.get(name="juno"),
            hostname="juno-01",
            health=Device.HEALTH_GOOD,
        )
        self.assertEqual("juno", device.get_extends())
        self.assertEqual("juno", device.device_type.name)
