from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase

from lava_scheduler_app.models import (
    GroupDevicePermission,
    GroupDeviceTypePermission,
    TestJob,
)
from lava_server.backends import GroupPermissionBackend, is_object_supported
from tests.lava_scheduler_app.test_submission import TestCaseWithFactory

User = get_user_model()


class BackendAuthTest(TestCaseWithFactory):
    def setUp(self):
        super().setUp()
        self.group = self.factory.make_group()
        self.user = self.factory.make_user()
        self.user.groups.add(self.group)

        self.definition = self.factory.make_job_data_from_file(
            "qemu-pipeline-first-job.yaml"
        )
        self.device_type = self.factory.make_device_type(name="qemu")
        self.device = self.factory.make_device(
            device_type=self.device_type, hostname="qemu-1"
        )
        self.job = TestJob.from_yaml_and_user(self.definition, self.user)
        self.backend = GroupPermissionBackend()

    def tearDown(self):
        super().tearDown()
        GroupDeviceTypePermission.objects.all().delete()
        GroupDevicePermission.objects.all().delete()

    def test_is_object_supported(self):
        self.assertTrue(is_object_supported(self.device))
        self.assertTrue(is_object_supported(self.device_type))
        self.assertFalse(is_object_supported(self.user))
        self.assertFalse(is_object_supported(self.group))
        self.assertFalse(is_object_supported(self.job))

    def test_is_object_supported_none(self):
        self.assertFalse(is_object_supported(None))

    def test_get_all_permissions(self):
        GroupDevicePermission.objects.assign_perm(
            "view_device", self.group, self.device
        )
        self.assertEqual(
            {"view_device"},
            set(self.backend.get_all_permissions(self.user, self.device)),
        )
        GroupDevicePermission.objects.assign_perm(
            "change_device", self.group, self.device
        )
        self.assertEqual(
            {"change_device", "submit_to_device", "view_device"},
            set(self.backend.get_all_permissions(self.user, self.device)),
        )

        GroupDeviceTypePermission.objects.assign_perm(
            "view_devicetype", self.group, self.device_type
        )
        self.assertEqual(
            {"view_devicetype"},
            set(self.backend.get_all_permissions(self.user, self.device_type)),
        )
        GroupDeviceTypePermission.objects.assign_perm(
            "change_devicetype", self.group, self.device_type
        )
        self.assertEqual(
            {"change_devicetype", "view_devicetype", "submit_to_devicetype"},
            self.backend.get_all_permissions(self.user, self.device_type),
        )

    def test_has_perm(self):
        GroupDevicePermission.objects.assign_perm(
            "change_device", self.group, self.device
        )
        self.assertTrue(
            self.backend.has_perm(
                self.user, "lava_scheduler_app.change_device", self.device
            )
        )
        self.assertTrue(
            self.backend.has_perm(
                self.user, "lava_scheduler_app.submit_to_device", self.device
            )
        )
        self.assertFalse(
            self.backend.has_perm(
                self.user, "lava_scheduler_app.view_devicetype", self.device_type
            )
        )

    def test_has_global_perm(self):
        user = self.factory.make_user()
        user.user_permissions.add(Permission.objects.get(codename="change_device"))
        self.assertTrue(
            self.backend.has_perm(user, "lava_scheduler_app.change_device", self.device)
        )

    def test_has_perm_wrong_app_label(self):
        with TestCase.assertRaises(self, ValueError):
            self.backend.has_perm(
                self.user, "lava_results_app.change_device", self.device
            )
