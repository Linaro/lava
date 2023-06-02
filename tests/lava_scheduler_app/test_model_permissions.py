# Copyright (C) 2019 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission

from lava_scheduler_app.models import (
    Device,
    DeviceType,
    GroupDevicePermission,
    GroupDeviceTypePermission,
    GroupWorkerPermission,
    TestJob,
    Worker,
)
from tests.lava_scheduler_app.test_submission import TestCaseWithFactory

User = get_user_model()


class ModelPermissionsTest(TestCaseWithFactory):
    def setUp(self):
        super().setUp()
        self.admin_user = User.objects.create(
            username=self.factory.get_unique_user(), is_superuser=True
        )
        # set up auth data.
        self.group1 = self.factory.make_group(name="test-group1")
        self.group2 = self.factory.make_group(name="test-group2")
        self.user1 = self.factory.make_user()
        self.user1.groups.add(self.group1)
        self.user2 = self.factory.make_user()
        self.user2.groups.add(self.group2)
        self.user3 = self.factory.make_user()

        # create workers
        self.worker1 = Worker.objects.create(
            hostname="worker-1", state=Worker.STATE_ONLINE
        )

        # Create device types.
        self.qemu_device_type = self.factory.make_device_type(name="qemu")
        self.bbb_device_type = self.factory.make_device_type(name="bbb")
        self.lxc_device_type = self.factory.make_device_type(name="lxc")
        self.all_device_types = [
            self.qemu_device_type,
            self.bbb_device_type,
            self.lxc_device_type,
        ]

        # Create devices.
        self.qemu_device1 = self.factory.make_device(
            device_type=self.qemu_device_type, hostname="qemu-1"
        )
        self.qemu_device2 = self.factory.make_device(
            device_type=self.qemu_device_type, hostname="qemu-2"
        )
        self.qemu_device3 = self.factory.make_device(
            device_type=self.qemu_device_type, hostname="qemu-3"
        )
        self.all_qemu_devices = [
            self.qemu_device1,
            self.qemu_device2,
            self.qemu_device3,
        ]

        self.bbb_device1 = self.factory.make_device(
            device_type=self.bbb_device_type, hostname="bbb-1"
        )
        self.bbb_device2 = self.factory.make_device(
            device_type=self.bbb_device_type, hostname="bbb-2"
        )
        self.all_bbb_devices = [self.bbb_device1, self.bbb_device2]

        self.all_devices = self.all_qemu_devices + self.all_bbb_devices

        self.definition = self.factory.make_job_data_from_file("qemu.yaml")
        # Create testjobs.
        self.qemu_job1 = TestJob.from_yaml_and_user(self.definition, self.admin_user)
        self.qemu_job2 = TestJob.from_yaml_and_user(self.definition, self.admin_user)
        self.all_bbb_jobs = TestJob.from_yaml_and_user(
            self.factory.make_job_data_from_file("bbb-bbb-vland-group.yaml"),
            self.admin_user,
        )
        self.bbb_job1 = self.all_bbb_jobs[0]
        self.bbb_job2 = self.all_bbb_jobs[1]
        self.all_qemu_jobs = [self.qemu_job1, self.qemu_job2]
        self.all_jobs = self.all_qemu_jobs + self.all_bbb_jobs

    def tearDown(self):
        super().tearDown()
        GroupDeviceTypePermission.objects.all().delete()
        GroupDevicePermission.objects.all().delete()
        GroupWorkerPermission.objects.all().delete()
        TestJob.objects.all().delete()

    def test_device_type_is_permission_restricted(self):
        self.assertFalse(
            self.qemu_device_type.is_permission_restricted(DeviceType.VIEW_PERMISSION)
        )

        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.VIEW_PERMISSION, self.group1, self.qemu_device_type
        )
        self.assertTrue(
            self.qemu_device_type.is_permission_restricted(DeviceType.VIEW_PERMISSION)
        )
        self.assertFalse(
            self.qemu_device_type.is_permission_restricted(DeviceType.CHANGE_PERMISSION)
        )
        self.assertFalse(
            self.bbb_device_type.is_permission_restricted(DeviceType.VIEW_PERMISSION)
        )

        GroupDeviceTypePermission.objects.all().delete()
        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.CHANGE_PERMISSION, self.group1, self.qemu_device_type
        )
        self.assertFalse(
            self.qemu_device_type.is_permission_restricted(DeviceType.VIEW_PERMISSION)
        )
        self.assertTrue(
            self.qemu_device_type.is_permission_restricted(DeviceType.CHANGE_PERMISSION)
        )

    def test_device_type_can_view_anonymous(self):
        self.assertTrue(self.qemu_device_type.can_view(AnonymousUser()))

        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.VIEW_PERMISSION, self.group1, self.qemu_device_type
        )
        self.assertFalse(self.qemu_device_type.can_view(AnonymousUser()))

    def test_device_type_can_view(self):
        self.assertTrue(self.qemu_device_type.can_view(self.user1))
        self.assertTrue(self.qemu_device_type.can_view(self.user2))

        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.VIEW_PERMISSION, self.group1, self.qemu_device_type
        )
        delattr(self.user1, "_cached_has_perm")
        delattr(self.user2, "_cached_has_perm")
        self.assertTrue(self.qemu_device_type.can_view(self.user1))
        self.assertFalse(self.qemu_device_type.can_view(self.user2))

    def test_device_can_view_anonymous(self):
        self.assertTrue(self.qemu_device1.can_view(AnonymousUser()))

        GroupDevicePermission.objects.assign_perm(
            Device.VIEW_PERMISSION, self.group1, self.qemu_device1
        )
        self.assertFalse(self.qemu_device1.can_view(AnonymousUser()))

    def test_device_can_view_anonymous_through_device_type(self):
        self.assertTrue(self.qemu_device1.can_view(AnonymousUser()))

        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.VIEW_PERMISSION, self.group1, self.qemu_device_type
        )
        self.assertFalse(self.qemu_device1.can_view(AnonymousUser()))
        self.assertFalse(self.qemu_device2.can_view(AnonymousUser()))
        self.assertTrue(self.bbb_device1.can_view(AnonymousUser()))

    def test_device_can_view(self):
        self.assertTrue(self.qemu_device1.can_view(self.user1))
        self.assertTrue(self.qemu_device1.can_view(self.user2))

        GroupDevicePermission.objects.assign_perm(
            Device.VIEW_PERMISSION, self.group1, self.qemu_device1
        )
        delattr(self.user1, "_cached_has_perm")
        delattr(self.user2, "_cached_has_perm")
        self.assertTrue(self.qemu_device1.can_view(self.user1))
        self.assertFalse(self.qemu_device1.can_view(self.user2))

    def test_device_can_view_through_device_type(self):
        self.assertTrue(self.qemu_device1.can_view(self.user1))
        self.assertTrue(self.qemu_device1.can_view(self.user2))

        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.VIEW_PERMISSION, self.group1, self.qemu_device_type
        )
        delattr(self.user1, "_cached_has_perm")
        delattr(self.user2, "_cached_has_perm")
        self.assertTrue(self.qemu_device1.can_view(self.user1))
        self.assertTrue(self.qemu_device2.can_view(self.user1))
        self.assertFalse(self.qemu_device1.can_view(self.user2))
        self.assertFalse(self.qemu_device2.can_view(self.user2))

    def test_device_can_change(self):
        self.assertFalse(self.qemu_device1.can_change(self.user1))
        self.assertFalse(self.qemu_device1.can_change(self.user2))

        GroupDevicePermission.objects.assign_perm(
            Device.CHANGE_PERMISSION, self.group1, self.qemu_device1
        )
        delattr(self.user1, "_cached_has_perm")
        delattr(self.user2, "_cached_has_perm")
        self.assertTrue(self.qemu_device1.can_change(self.user1))
        self.assertFalse(self.qemu_device1.can_change(self.user2))

    def test_device_can_change_through_device_type(self):
        self.assertFalse(self.qemu_device1.can_change(self.user1))
        self.assertFalse(self.qemu_device1.can_change(self.user2))

        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.CHANGE_PERMISSION, self.group1, self.qemu_device_type
        )
        delattr(self.user1, "_cached_has_perm")
        delattr(self.user2, "_cached_has_perm")
        self.assertTrue(self.qemu_device1.can_change(self.user1))
        self.assertFalse(self.qemu_device1.can_change(self.user2))

    def test_device_can_submit(self):
        self.assertTrue(self.qemu_device1.can_submit(self.user1))
        self.assertTrue(self.qemu_device1.can_submit(self.user2))
        self.assertFalse(self.qemu_device1.can_submit(AnonymousUser()))

        GroupDevicePermission.objects.assign_perm(
            Device.SUBMIT_PERMISSION, self.group1, self.qemu_device1
        )
        delattr(self.user1, "_cached_has_perm")
        delattr(self.user2, "_cached_has_perm")
        self.assertTrue(self.qemu_device1.can_submit(self.user1))
        self.assertFalse(self.qemu_device1.can_submit(self.user2))

    def test_device_can_submit_through_device_type(self):
        self.assertTrue(self.qemu_device1.can_submit(self.user1))
        self.assertTrue(self.qemu_device1.can_submit(self.user2))

        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.SUBMIT_PERMISSION, self.group1, self.qemu_device_type
        )
        self.assertTrue(self.qemu_device1.can_submit(self.user1))
        self.assertFalse(self.qemu_device1.can_submit(self.user2))

    def test_testjob_can_view_anonymous(self):
        self.assertTrue(self.qemu_job1.can_view(AnonymousUser()))

        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.VIEW_PERMISSION, self.group1, self.qemu_device_type
        )
        self.assertFalse(self.qemu_job1.can_view(AnonymousUser()))

    def test_testjob_can_view_anonymous_through_device_type(self):
        self.assertTrue(self.qemu_job1.can_view(AnonymousUser()))
        self.assertTrue(self.bbb_job1.can_view(AnonymousUser()))

        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.VIEW_PERMISSION, self.group1, self.qemu_device_type
        )
        self.assertFalse(self.qemu_job1.can_view(AnonymousUser()))
        self.assertFalse(self.qemu_job2.can_view(AnonymousUser()))
        self.assertTrue(self.bbb_job1.can_view(AnonymousUser()))

    def test_testjob_can_view_anonymous_through_device(self):
        self.qemu_job1.actual_device = self.qemu_device1
        self.qemu_job1.save()
        self.assertTrue(self.qemu_job1.can_view(AnonymousUser()))

        GroupDevicePermission.objects.assign_perm(
            Device.VIEW_PERMISSION, self.group1, self.qemu_device1
        )

        self.assertFalse(self.qemu_job1.can_view(AnonymousUser()))
        self.assertTrue(self.bbb_job1.can_view(AnonymousUser()))

    def test_testjob_can_view(self):
        self.assertTrue(self.qemu_job1.can_view(self.user1))
        self.assertTrue(self.qemu_job1.can_view(self.user2))

    def test_testjob_can_view_private(self):
        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.VIEW_PERMISSION, self.group1, self.qemu_device_type
        )

        self.assertTrue(self.qemu_job1.can_view(self.user1))
        self.assertFalse(self.qemu_job1.can_view(self.user2))

        self.qemu_job1.is_public = False
        self.qemu_job1.save()
        self.assertFalse(self.qemu_job1.can_view(self.user1))
        self.assertFalse(self.qemu_job1.can_view(self.user2))

    def test_testjob_can_view_viewing_groups(self):
        self.qemu_job1.viewing_groups.add(self.group2)
        self.assertFalse(self.qemu_job1.can_view(self.user1))
        self.assertTrue(self.qemu_job1.can_view(self.user2))
        self.assertTrue(self.qemu_job1.can_view(self.admin_user))

    def test_testjob_can_view_viewing_groups_multiple_groups(self):
        self.qemu_job1.viewing_groups.add(self.group1, self.group2)
        self.assertFalse(self.qemu_job1.can_view(self.user1))
        self.assertFalse(self.qemu_job1.can_view(self.user2))
        self.user3.groups.add(self.group1, self.group2)
        self.assertTrue(self.qemu_job1.can_view(self.user3))
        self.assertTrue(self.qemu_job1.can_view(self.admin_user))

    def test_testjob_can_view_viewing_groups_with_perm_restrictions(self):
        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.VIEW_PERMISSION, self.group1, self.qemu_device_type
        )

        self.qemu_job1.viewing_groups.add(self.group2)
        self.assertFalse(self.qemu_job1.can_view(self.user1))
        self.assertTrue(self.qemu_job1.can_view(self.user2))

    def test_testjob_can_view_through_device_type(self):
        self.assertTrue(self.qemu_job1.can_view(self.user1))
        self.assertTrue(self.qemu_job1.can_view(self.user2))

        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.VIEW_PERMISSION, self.group1, self.qemu_device_type
        )
        delattr(self.user1, "_cached_has_perm")
        delattr(self.user2, "_cached_has_perm")
        self.assertTrue(self.qemu_job1.can_view(self.user1))
        self.assertTrue(self.qemu_job2.can_view(self.user1))
        self.assertFalse(self.qemu_job1.can_view(self.user2))
        self.assertFalse(self.qemu_job2.can_view(self.user2))

    def test_testjob_can_view_through_device(self):
        self.qemu_job1.actual_device = self.qemu_device1
        self.qemu_job1.save()
        self.assertTrue(self.qemu_job1.can_view(self.user1))
        self.assertTrue(self.qemu_job1.can_view(self.user2))

        GroupDevicePermission.objects.assign_perm(
            Device.VIEW_PERMISSION, self.group1, self.qemu_device1
        )
        delattr(self.user1, "_cached_has_perm")
        delattr(self.user2, "_cached_has_perm")
        self.assertTrue(self.qemu_job1.can_view(self.user1))
        self.assertFalse(self.qemu_job1.can_view(self.user2))

    def test_testjob_can_change(self):
        self.assertFalse(self.qemu_job1.can_change(self.user1))
        self.assertFalse(self.qemu_job1.can_change(self.user2))
        self.assertFalse(self.qemu_job1.can_change(AnonymousUser()))

    def test_testjob_can_change_through_device_type(self):
        self.assertFalse(self.qemu_job1.can_change(self.user1))
        self.assertFalse(self.qemu_job1.can_change(self.user2))

        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.CHANGE_PERMISSION, self.group1, self.qemu_device_type
        )
        delattr(self.user1, "_cached_has_perm")
        delattr(self.user2, "_cached_has_perm")
        self.assertTrue(self.qemu_job1.can_change(self.user1))
        self.assertFalse(self.qemu_job1.can_change(self.user2))

    def test_testjob_can_change_through_device(self):
        self.qemu_job1.actual_device = self.qemu_device1
        self.qemu_job1.save()
        self.assertFalse(self.qemu_job1.can_change(self.user1))
        self.assertFalse(self.qemu_job1.can_change(self.user2))

        GroupDevicePermission.objects.assign_perm(
            Device.CHANGE_PERMISSION, self.group1, self.qemu_device1
        )
        delattr(self.user1, "_cached_has_perm")
        delattr(self.user2, "_cached_has_perm")
        self.assertTrue(self.qemu_job1.can_change(self.user1))
        self.assertFalse(self.qemu_job1.can_change(self.user2))

    def test_testjob_can_resubmit(self):
        self.qemu_job1.actual_device = self.qemu_device1
        self.qemu_job1.save()
        self.assertTrue(self.qemu_job1.can_resubmit(self.user1))
        self.assertTrue(self.qemu_job1.can_resubmit(self.user2))
        self.assertFalse(self.qemu_job1.can_resubmit(AnonymousUser()))

        GroupDevicePermission.objects.assign_perm(
            Device.SUBMIT_PERMISSION, self.group1, self.qemu_device1
        )
        delattr(self.user1, "_cached_has_perm")
        delattr(self.user2, "_cached_has_perm")
        self.assertTrue(self.qemu_job1.can_resubmit(self.user1))
        self.assertFalse(self.qemu_job1.can_resubmit(self.user2))

    def test_testjob_can_resubmit_through_device_type(self):
        self.assertFalse(self.qemu_job1.can_resubmit(self.user1))
        self.assertFalse(self.qemu_job1.can_resubmit(self.user2))

        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.SUBMIT_PERMISSION, self.group1, self.qemu_device_type
        )
        delattr(self.user1, "_cached_has_perm")
        delattr(self.user2, "_cached_has_perm")
        self.assertTrue(self.qemu_job1.can_resubmit(self.user1))
        self.assertFalse(self.qemu_job1.can_resubmit(self.user2))

    def test_testjob_can_view_global_permission(self):
        self.user2.user_permissions.add(
            Permission.objects.get(name="Can submit jobs to device")
        )

        self.assertTrue(self.qemu_device1.can_submit(self.user2))

    def test_worker_is_permission_restricted(self):
        self.assertFalse(
            self.worker1.is_permission_restricted(Worker.CHANGE_PERMISSION)
        )

        GroupWorkerPermission.objects.assign_perm(
            Worker.CHANGE_PERMISSION, self.group1, self.worker1
        )
        self.assertTrue(self.worker1.is_permission_restricted(Worker.CHANGE_PERMISSION))

    def test_worker_can_change_anonymous(self):
        self.assertFalse(self.worker1.can_change(AnonymousUser()))

        GroupWorkerPermission.objects.assign_perm(
            Worker.CHANGE_PERMISSION, self.group1, self.worker1
        )
        self.assertFalse(self.worker1.can_change(AnonymousUser()))

    def test_worker_can_change_admin(self):
        self.assertTrue(self.worker1.can_change(self.admin_user))

        GroupWorkerPermission.objects.assign_perm(
            Worker.CHANGE_PERMISSION, self.group1, self.worker1
        )
        self.assertTrue(self.worker1.can_change(self.admin_user))

    def test_worker_can_change(self):
        self.assertFalse(self.worker1.can_change(self.user1))
        self.assertFalse(self.worker1.can_change(self.user2))

        GroupWorkerPermission.objects.assign_perm(
            Worker.CHANGE_PERMISSION, self.group1, self.worker1
        )
        delattr(self.user1, "_cached_has_perm")
        delattr(self.user2, "_cached_has_perm")
        self.assertTrue(self.worker1.can_change(self.user1))
        self.assertFalse(self.worker1.can_change(self.user2))
