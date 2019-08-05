# -*- coding: utf-8 -*-
# Copyright (C) 2019 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA.  If not, see <http://www.gnu.org/licenses/>.


from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission

from lava_scheduler_app.models import (
    GroupDeviceTypePermission,
    GroupDevicePermission,
    DeviceType,
    TestJob,
    Device,
)
from lava_scheduler_app.tests.test_submission import TestCaseWithFactory

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
            self.qemu_device_type.is_permission_restricted(DeviceType.ADMIN_PERMISSION)
        )
        self.assertFalse(
            self.bbb_device_type.is_permission_restricted(DeviceType.VIEW_PERMISSION)
        )

        GroupDeviceTypePermission.objects.all().delete()
        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.ADMIN_PERMISSION, self.group1, self.qemu_device_type
        )
        self.assertFalse(
            self.qemu_device_type.is_permission_restricted(DeviceType.VIEW_PERMISSION)
        )
        self.assertTrue(
            self.qemu_device_type.is_permission_restricted(DeviceType.ADMIN_PERMISSION)
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
        self.assertTrue(self.qemu_device1.can_view(self.user1))
        self.assertFalse(self.qemu_device1.can_view(self.user2))

    def test_device_can_view_through_device_type(self):

        self.assertTrue(self.qemu_device1.can_view(self.user1))
        self.assertTrue(self.qemu_device1.can_view(self.user2))

        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.VIEW_PERMISSION, self.group1, self.qemu_device_type
        )
        self.assertTrue(self.qemu_device1.can_view(self.user1))
        self.assertTrue(self.qemu_device2.can_view(self.user1))
        self.assertFalse(self.qemu_device1.can_view(self.user2))
        self.assertFalse(self.qemu_device2.can_view(self.user2))

    def test_device_can_admin(self):

        self.assertFalse(self.qemu_device1.can_admin(self.user1))
        self.assertFalse(self.qemu_device1.can_admin(self.user2))

        GroupDevicePermission.objects.assign_perm(
            Device.ADMIN_PERMISSION, self.group1, self.qemu_device1
        )
        self.assertTrue(self.qemu_device1.can_admin(self.user1))
        self.assertFalse(self.qemu_device1.can_admin(self.user2))

    def test_device_can_admin_through_device_type(self):

        self.assertFalse(self.qemu_device1.can_admin(self.user1))
        self.assertFalse(self.qemu_device1.can_admin(self.user2))

        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.ADMIN_PERMISSION, self.group1, self.qemu_device_type
        )
        self.assertTrue(self.qemu_device1.can_admin(self.user1))
        self.assertFalse(self.qemu_device1.can_admin(self.user2))

    def test_device_can_submit(self):

        self.assertTrue(self.qemu_device1.can_submit(self.user1))
        self.assertTrue(self.qemu_device1.can_submit(self.user2))
        self.assertFalse(self.qemu_device1.can_submit(AnonymousUser()))

        GroupDevicePermission.objects.assign_perm(
            Device.SUBMIT_PERMISSION, self.group1, self.qemu_device1
        )
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
        self.assertTrue(self.qemu_job1.can_view(self.user1))
        self.assertFalse(self.qemu_job1.can_view(self.user2))

    def test_testjob_can_admin(self):

        self.assertFalse(self.qemu_job1.can_admin(self.user1))
        self.assertFalse(self.qemu_job1.can_admin(self.user2))
        self.assertFalse(self.qemu_job1.can_admin(AnonymousUser()))

    def test_testjob_can_admin_through_device_type(self):

        self.assertFalse(self.qemu_job1.can_admin(self.user1))
        self.assertFalse(self.qemu_job1.can_admin(self.user2))

        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.ADMIN_PERMISSION, self.group1, self.qemu_device_type
        )
        self.assertTrue(self.qemu_job1.can_admin(self.user1))
        self.assertFalse(self.qemu_job1.can_admin(self.user2))

    def test_testjob_can_admin_through_device(self):

        self.qemu_job1.actual_device = self.qemu_device1
        self.qemu_job1.save()
        self.assertFalse(self.qemu_job1.can_admin(self.user1))
        self.assertFalse(self.qemu_job1.can_admin(self.user2))

        GroupDevicePermission.objects.assign_perm(
            Device.ADMIN_PERMISSION, self.group1, self.qemu_device1
        )
        self.assertTrue(self.qemu_job1.can_admin(self.user1))
        self.assertFalse(self.qemu_job1.can_admin(self.user2))

    def test_testjob_can_view_global_permission(self):
        self.user2.user_permissions.add(
            Permission.objects.get(name="Can submit jobs to device")
        )

        self.assertTrue(self.qemu_device1.can_submit(self.user2))
