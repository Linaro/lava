from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase

from lava_server.backends import GroupPermissionBackend, is_object_supported
from lava_scheduler_app.models import GroupObjectPermission, TestJob
from lava_scheduler_app.tests.test_submission import TestCaseWithFactory

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
        GroupObjectPermission.objects.all().delete()

    def test_is_object_supported(self):
        self.assertTrue(is_object_supported(self.job))
        self.assertTrue(is_object_supported(self.device))
        self.assertTrue(is_object_supported(self.device_type))
        self.assertFalse(is_object_supported(self.user))
        self.assertFalse(is_object_supported(self.group))

    def test_is_object_supported_none(self):
        self.assertFalse(is_object_supported(None))

    def test_get_all_permissions(self):
        GroupObjectPermission.objects.assign_perm(
            "view_device", self.group, self.device
        )
        self.assertEqual(
            set(["view_device"]),
            set(self.backend.get_all_permissions(self.user, self.device)),
        )
        GroupObjectPermission.objects.assign_perm(
            "admin_device", self.group, self.device
        )
        self.assertEqual(
            set(["admin_device", "submit_to_device", "view_device"]),
            set(self.backend.get_all_permissions(self.user, self.device)),
        )

        GroupObjectPermission.objects.assign_perm("view_testjob", self.group, self.job)
        self.assertEqual(
            set(["view_testjob"]),
            set(self.backend.get_all_permissions(self.user, self.job)),
        )
        GroupObjectPermission.objects.assign_perm("admin_testjob", self.group, self.job)
        self.assertEqual(
            set(["admin_testjob", "view_testjob", "cancel_resubmit_testjob"]),
            self.backend.get_all_permissions(self.user, self.job),
        )

    def test_has_perm(self):
        GroupObjectPermission.objects.assign_perm("admin_testjob", self.group, self.job)
        self.assertTrue(self.backend.has_perm(self.user, "admin_testjob", self.job))
        self.assertTrue(
            self.backend.has_perm(
                self.user, "lava_scheduler_app.admin_testjob", self.job
            )
        )
        self.assertTrue(
            self.backend.has_perm(self.user, "cancel_resubmit_testjob", self.job)
        )
        self.assertFalse(self.backend.has_perm(self.user, "view_device", self.device))

    def test_has_global_perm(self):
        user = self.factory.make_user()
        user.user_permissions.add(Permission.objects.get(codename="admin_testjob"))
        self.assertTrue(self.backend.has_perm(user, "admin_testjob", self.job))
        self.assertTrue(
            self.backend.has_perm(user, "lava_scheduler_app.admin_testjob", self.job)
        )

    def test_has_perm_wrong_app_label(self):
        GroupObjectPermission.objects.assign_perm("admin_testjob", self.group, self.job)
        with TestCase.assertRaises(self, ValueError):
            self.backend.has_perm(self.user, "lava_results_app.admin_testjob", self.job)
