# Copyright (C) 2019 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test import TestCase

from lava_common.exceptions import ObjectNotPersisted, PermissionNameError
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


class ManagersTest(TestCaseWithFactory):
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
        self.worker2 = Worker.objects.create(
            hostname="worker-2", state=Worker.STATE_OFFLINE
        )
        self.worker3 = Worker.objects.create(
            hostname="worker-3", state=Worker.STATE_ONLINE
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

    def test_assign_perm(self):
        # Test assign permission.
        GroupDevicePermission.objects.assign_perm(
            "change_device", self.group1, self.qemu_device1
        )
        self.assertTrue(
            self.user1.has_perm(Device.CHANGE_PERMISSION, self.qemu_device1)
        )

    def test_assign_perm_not_persisted(self):
        device = Device()
        with TestCase.assertRaises(self, ObjectNotPersisted):
            GroupDevicePermission.objects.assign_perm(
                "change_device", self.group1, device
            )

    def test_assign_perm_wrong_permission_name(self):
        # Test wrong permission name when assigning permission.
        with TestCase.assertRaises(self, PermissionNameError):
            GroupDevicePermission.objects.assign_perm(
                Device.CHANGE_PERMISSION, self.group1, self.qemu_device_type
            )

    def test_remove_perm(self):
        GroupDevicePermission.objects.assign_perm(
            "change_device", self.group1, self.qemu_device1
        )
        self.assertTrue(
            self.user1.has_perm(Device.CHANGE_PERMISSION, self.qemu_device1)
        )
        GroupDevicePermission.objects.remove_perm(
            "change_device", self.group1, self.qemu_device1
        )
        delattr(self.user1, "_cached_has_perm")
        self.assertFalse(
            self.user1.has_perm(Device.CHANGE_PERMISSION, self.qemu_device1)
        )

    def test_bulk_assign_perm(self):
        # Test bulk assign permission.
        GroupDevicePermission.objects.bulk_assign_perm(
            "change_device", self.group1, Device.objects.all()
        )
        self.assertTrue(
            self.user1.has_perm(Device.CHANGE_PERMISSION, self.qemu_device1)
        )
        self.assertTrue(
            self.user1.has_perm(Device.CHANGE_PERMISSION, self.qemu_device2)
        )
        self.assertTrue(self.user1.has_perm(Device.CHANGE_PERMISSION, self.bbb_device1))
        self.assertTrue(self.user1.has_perm(Device.CHANGE_PERMISSION, self.bbb_device2))
        self.assertFalse(
            self.user2.has_perm(Device.CHANGE_PERMISSION, self.qemu_device1)
        )

    def test_assign_perm_to_many(self):
        # Test assign perm to many groups.
        GroupDevicePermission.objects.assign_perm_to_many(
            "change_device", [self.group1, self.group2], self.qemu_device1
        )
        self.assertTrue(
            self.user1.has_perm(Device.CHANGE_PERMISSION, self.qemu_device1)
        )
        self.assertTrue(
            self.user2.has_perm(Device.CHANGE_PERMISSION, self.qemu_device1)
        )
        self.assertFalse(
            self.user2.has_perm(Device.CHANGE_PERMISSION, self.qemu_device2)
        )

    def test_restricted_by_perm(self):
        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.CHANGE_PERMISSION, self.group1, self.qemu_device_type
        )
        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.VIEW_PERMISSION, self.group1, self.bbb_device_type
        )
        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.VIEW_PERMISSION, self.group1, self.lxc_device_type
        )

        # Test that qemu is not restricted by view permission.
        self.assertEqual(
            set(
                DeviceType.objects.visible_by_user(
                    AnonymousUser(),
                )
            ),
            {self.qemu_device_type},
        )

        # Test that lxc and bbb are not restricted by admin permission.
        self.assertEqual(
            set(
                DeviceType.objects.filter_by_perm(
                    DeviceType.CHANGE_PERMISSION,
                    AnonymousUser(),
                    include_objects_without_permissions=True,
                )
            ),
            {self.lxc_device_type, self.bbb_device_type},
        )

        # Test that all are not restricted by submit permission.
        self.assertEqual(
            set(
                DeviceType.objects.filter_by_perm(
                    DeviceType.SUBMIT_PERMISSION,
                    AnonymousUser(),
                    include_objects_without_permissions=True,
                )
            ),
            {self.lxc_device_type, self.bbb_device_type, self.qemu_device_type},
        )

    def test_filter_by_perm_single_group(self):
        settings.DEBUG = True
        try:
            ContentType.objects.clear_cache()

            GroupDevicePermission.objects.assign_perm(
                "change_device", self.group1, self.qemu_device1
            )
            GroupDevicePermission.objects.assign_perm(
                "submit_to_device", self.group1, self.qemu_device2
            )

            qemu_devices_queryset = Device.objects.filter(
                device_type=self.qemu_device_type
            )

            queryset = qemu_devices_queryset.filter_by_perm(
                "lava_scheduler_app.submit_to_device", self.user1
            )
            self.assertEqual(set(queryset), {self.qemu_device1, self.qemu_device2})

            queryset = qemu_devices_queryset.filter_by_perm(
                "lava_scheduler_app.change_device", self.user1
            )
            self.assertEqual(set(queryset), {self.qemu_device1})

            queryset = qemu_devices_queryset.filter_by_perm(
                "lava_scheduler_app.view_device", self.user1
            )
            self.assertEqual(set(queryset), {self.qemu_device1, self.qemu_device2})

            queryset = qemu_devices_queryset.filter_by_perm(
                "lava_scheduler_app.submit_to_device", self.user1
            )

            GroupDevicePermission.objects.assign_perm(
                "submit_to_device", self.group1, self.qemu_device1
            )
            query_count = len(connection.queries)

            queryset = queryset.filter_by_perm(
                "lava_scheduler_app.submit_to_device", self.user1
            )
            self.assertEqual(set(queryset), {self.qemu_device1, self.qemu_device2})
            self.assertEqual(len(connection.queries), query_count + 1)
        finally:
            settings.DEBUG = False

    def test_filter_by_perm_multiple_groups(self):
        group1 = self.factory.make_group(name="test_group1")
        group2 = self.factory.make_group(name="test_group2")
        group3 = self.factory.make_group(name="test_group3")
        user1 = self.factory.make_user()
        user1.groups.add(group1)
        user1.groups.add(group2)

        # Assign permissions.
        GroupDevicePermission.objects.assign_perm(
            "change_device", group1, self.qemu_device1
        )
        GroupDevicePermission.objects.assign_perm(
            "submit_to_device", group2, self.qemu_device2
        )

        qemu_devices_queryset = Device.objects.filter(device_type=self.qemu_device_type)

        # user1 has submit_to permissions for devices 1 and 2, but not 3
        queryset = qemu_devices_queryset.filter_by_perm(
            "lava_scheduler_app.submit_to_device", user1
        )
        self.assertEqual(set(queryset), {self.qemu_device1, self.qemu_device2})

        # user1 has admin permission for device1.
        queryset = qemu_devices_queryset.filter_by_perm(
            "lava_scheduler_app.change_device", user1
        )
        self.assertEqual(set(queryset), {self.qemu_device1})

        # user1 has view permissions for devices 1 and 2.
        queryset = qemu_devices_queryset.filter_by_perm(
            "lava_scheduler_app.view_device", user1
        )
        self.assertEqual(set(queryset), {self.qemu_device1, self.qemu_device2})

        # user1 has both submit and admin permissions for devices 1 and 2.
        queryset = qemu_devices_queryset.filter_by_perm(
            "lava_scheduler_app.submit_to_device", user1
        )
        self.assertEqual(set(queryset), {self.qemu_device1, self.qemu_device2})

        # Enter user 2.
        user2 = self.factory.make_user()
        user2.groups.add(group2)

        queryset = qemu_devices_queryset.filter_by_perm(
            "lava_scheduler_app.submit_to_device", user2
        )
        self.assertEqual(set(queryset), {self.qemu_device2})

        queryset = qemu_devices_queryset.filter_by_perm(
            "lava_scheduler_app.change_device", user2
        )
        self.assertEqual(set(queryset), set())

        queryset = qemu_devices_queryset.filter_by_perm(
            "lava_scheduler_app.view_device", user2
        )
        self.assertEqual(set(queryset), {self.qemu_device2})

    def test_devicetype_manager_view(self):
        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.CHANGE_PERMISSION, self.group1, self.qemu_device_type
        )
        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.VIEW_PERMISSION, self.group1, self.bbb_device_type
        )

        # user1 can see all 3 device types.
        self.assertEqual(
            set(DeviceType.objects.all().visible_by_user(self.user1)),
            set(self.all_device_types),
        )
        # user2 can view only qemu and lxc device types.
        self.assertEqual(
            set(DeviceType.objects.all().visible_by_user(self.user2)),
            {self.qemu_device_type, self.lxc_device_type},
        )
        # same as above, use different method.
        self.assertEqual(
            set(
                DeviceType.objects.all().accessible_by_user(
                    self.user2, DeviceType.VIEW_PERMISSION
                )
            ),
            {self.qemu_device_type, self.lxc_device_type},
        )
        # AnonymousUser can see also see all device types which are not view
        # restricted.
        self.assertEqual(
            set(DeviceType.objects.all().visible_by_user(AnonymousUser())),
            {self.qemu_device_type, self.lxc_device_type},
        )

    def test_devicetype_manager_accessible_wrong_permission(self):
        with TestCase.assertRaises(self, ValueError):
            DeviceType.objects.all().accessible_by_user(self.user1, "non_existing_perm")

    def test_devicetype_manager_accessible(self):
        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.CHANGE_PERMISSION, self.group1, self.qemu_device_type
        )
        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.SUBMIT_PERMISSION, self.group1, self.qemu_device_type
        )

        # user1 can admin only qemu.
        self.assertEqual(
            set(
                DeviceType.objects.all().accessible_by_user(
                    self.user1, DeviceType.CHANGE_PERMISSION
                )
            ),
            {self.qemu_device_type},
        )
        # user1 can submit to all.
        self.assertEqual(
            set(
                DeviceType.objects.all().accessible_by_user(
                    self.user1, DeviceType.SUBMIT_PERMISSION
                )
            ),
            set(self.all_device_types),
        )

        # user2 can not admin anything.
        self.assertEqual(
            list(
                DeviceType.objects.all().accessible_by_user(
                    self.user2, DeviceType.CHANGE_PERMISSION
                )
            ),
            [],
        )
        # user2 can submit to all non-submit restricted device types.
        self.assertEqual(
            set(
                DeviceType.objects.all().accessible_by_user(
                    self.user2, DeviceType.SUBMIT_PERMISSION
                )
            ),
            {self.bbb_device_type, self.lxc_device_type},
        )

        # anonymous can not admin anything.
        self.assertEqual(
            list(
                DeviceType.objects.all().accessible_by_user(
                    AnonymousUser(), DeviceType.CHANGE_PERMISSION
                )
            ),
            [],
        )
        # anonymous can not submit anything.
        self.assertEqual(
            list(
                DeviceType.objects.all().accessible_by_user(
                    AnonymousUser(), DeviceType.SUBMIT_PERMISSION
                )
            ),
            [],
        )

    def test_devicetype_manager_view_global_permissions(self):
        self.user3.user_permissions.add(
            Permission.objects.get(name="Can view device type")
        )
        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.VIEW_PERMISSION, self.group1, self.bbb_device_type
        )

        # user3 can view all device types based on global permission.
        self.assertEqual(
            set(DeviceType.objects.all().visible_by_user(self.user3)),
            set(self.all_device_types),
        )

    def test_device_manager_view(self):
        # All users see everything before any permissions are assigned.
        self.assertEqual(
            set(Device.objects.all().visible_by_user(self.user1)), set(self.all_devices)
        )
        self.assertEqual(
            set(Device.objects.all().visible_by_user(self.user2)), set(self.all_devices)
        )
        self.assertEqual(
            set(Device.objects.all().visible_by_user(AnonymousUser())),
            set(self.all_devices),
        )

        GroupDevicePermission.objects.assign_perm(
            Device.VIEW_PERMISSION, self.group1, self.qemu_device2
        )

        # user1 should see everything since he has view_permission over
        # qemu device2 and the other ones are not view restricted
        self.assertEqual(
            set(
                Device.objects.filter(
                    device_type=self.qemu_device_type
                ).visible_by_user(self.user1)
            ),
            set(self.all_qemu_devices),
        )

        # user2 should see only devices which are not view restricted.
        self.assertEqual(
            set(
                Device.objects.filter(
                    device_type=self.qemu_device_type
                ).visible_by_user(self.user2)
            ),
            {self.qemu_device1, self.qemu_device3},
        )
        # AnonymousUser can see also see all devices which are not view
        # restricted.
        self.assertEqual(
            set(
                Device.objects.filter(
                    device_type=self.qemu_device_type
                ).visible_by_user(AnonymousUser())
            ),
            {self.qemu_device1, self.qemu_device3},
        )

    def test_device_manager_view_through_device_type(self):
        # Restrict the qemu device type. user1 should see all, user2 and
        # anonymous only bbb devices.
        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.VIEW_PERMISSION, self.group1, self.qemu_device_type
        )
        self.assertEqual(
            set(Device.objects.all().visible_by_user(self.user1)), set(self.all_devices)
        )
        self.assertEqual(
            set(Device.objects.all().visible_by_user(self.user2)),
            set(self.all_bbb_devices),
        )
        self.assertEqual(
            set(Device.objects.all().visible_by_user(AnonymousUser())),
            set(self.all_bbb_devices),
        )

        # Now give view permission for user2 and device3. user2 should see
        # device3 but user1 should not anymore. Anonymous still does not see
        # anything.
        GroupDevicePermission.objects.assign_perm(
            Device.VIEW_PERMISSION, self.group2, self.qemu_device3
        )
        self.assertEqual(
            set(
                Device.objects.filter(
                    device_type=self.qemu_device_type
                ).visible_by_user(self.user1)
            ),
            {self.qemu_device1, self.qemu_device2},
        )
        self.assertEqual(
            set(
                Device.objects.filter(
                    device_type=self.qemu_device_type
                ).visible_by_user(self.user2)
            ),
            {self.qemu_device3},
        )
        self.assertEqual(
            set(
                Device.objects.filter(
                    device_type=self.qemu_device_type
                ).visible_by_user(AnonymousUser())
            ),
            set(),
        )

    def test_device_manager_submit(self):
        # auth users can submit to all.
        self.assertEqual(
            set(
                Device.objects.all().accessible_by_user(
                    self.user1, Device.SUBMIT_PERMISSION
                )
            ),
            set(self.all_devices),
        )
        self.assertEqual(
            set(
                Device.objects.all().accessible_by_user(
                    self.user2, Device.SUBMIT_PERMISSION
                )
            ),
            set(self.all_devices),
        )
        # Anonymous can't do any of those.
        self.assertEqual(
            set(
                Device.objects.all().accessible_by_user(
                    AnonymousUser(), Device.SUBMIT_PERMISSION
                )
            ),
            set(),
        )

        GroupDevicePermission.objects.assign_perm(
            Device.SUBMIT_PERMISSION, self.group1, self.qemu_device2
        )
        # user1 should submit to everything since he has submit_permission over
        # qemu device2 and the other ones are not submission restricted
        self.assertEqual(
            set(
                Device.objects.filter(
                    device_type=self.qemu_device_type
                ).accessible_by_user(self.user1, Device.SUBMIT_PERMISSION)
            ),
            set(self.all_qemu_devices),
        )

        # user2 should only submit to devices which are not submission
        # restricted.
        self.assertEqual(
            set(
                Device.objects.filter(
                    device_type=self.qemu_device_type
                ).accessible_by_user(self.user2, Device.SUBMIT_PERMISSION)
            ),
            {self.qemu_device1, self.qemu_device3},
        )
        # AnonymousUser can still submit to none.
        self.assertEqual(
            set(
                Device.objects.all().accessible_by_user(
                    AnonymousUser(), Device.SUBMIT_PERMISSION
                )
            ),
            set(),
        )

    def test_device_manager_submit_through_device_type(self):
        # Restrict submission on qemu device type.
        # user1 should be still able to submit to eveything, user2 to
        # non-restricted and anonymous to none.
        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.SUBMIT_PERMISSION, self.group1, self.qemu_device_type
        )
        self.assertEqual(
            set(
                Device.objects.all().accessible_by_user(
                    self.user1, Device.SUBMIT_PERMISSION
                )
            ),
            set(self.all_devices),
        )
        self.assertEqual(
            set(
                Device.objects.all().accessible_by_user(
                    self.user2, Device.SUBMIT_PERMISSION
                )
            ),
            set(self.all_bbb_devices),
        )
        self.assertEqual(
            set(
                Device.objects.all().accessible_by_user(
                    AnonymousUser(), Device.SUBMIT_PERMISSION
                )
            ),
            set(),
        )

        # Now give submit permission for user2 and device3. user2 should be able
        # to submit to device3 but user1 should not anymore.
        # Anonymous still cannot submit to devices.
        GroupDevicePermission.objects.assign_perm(
            Device.SUBMIT_PERMISSION, self.group2, self.qemu_device3
        )
        self.assertEqual(
            set(
                Device.objects.filter(
                    device_type=self.qemu_device_type
                ).accessible_by_user(self.user1, Device.SUBMIT_PERMISSION)
            ),
            {self.qemu_device1, self.qemu_device2},
        )
        self.assertEqual(
            set(
                Device.objects.filter(
                    device_type=self.qemu_device_type
                ).accessible_by_user(self.user2, Device.SUBMIT_PERMISSION)
            ),
            {self.qemu_device3},
        )
        self.assertEqual(
            set(
                Device.objects.all().accessible_by_user(
                    AnonymousUser(), Device.SUBMIT_PERMISSION
                )
            ),
            set(),
        )

    def test_device_manager_admin(self):
        # auth users can admin none. Same goes for Anonymous
        self.assertEqual(
            set(
                Device.objects.all().accessible_by_user(
                    self.user1, Device.CHANGE_PERMISSION
                )
            ),
            set(),
        )
        self.assertEqual(
            set(
                Device.objects.all().accessible_by_user(
                    AnonymousUser(), Device.CHANGE_PERMISSION
                )
            ),
            set(),
        )

        GroupDevicePermission.objects.assign_perm(
            Device.CHANGE_PERMISSION, self.group1, self.qemu_device2
        )
        # user1 should be able to admin only qemu_device2
        self.assertEqual(
            set(
                Device.objects.all().accessible_by_user(
                    self.user1, Device.CHANGE_PERMISSION
                )
            ),
            {self.qemu_device2},
        )
        # user2 should not be able to admin anything
        self.assertEqual(
            set(
                Device.objects.all().accessible_by_user(
                    self.user2, Device.CHANGE_PERMISSION
                )
            ),
            set(),
        )
        # AnonymousUser can also still admin nothing.
        self.assertEqual(
            set(
                Device.objects.all().accessible_by_user(
                    AnonymousUser(), Device.CHANGE_PERMISSION
                )
            ),
            set(),
        )

    def test_device_manager_admin_through_device_type(self):
        # Allow admin on qemu device type to group1 (user1).
        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.CHANGE_PERMISSION, self.group1, self.qemu_device_type
        )

        self.assertEqual(
            set(
                Device.objects.all().accessible_by_user(
                    self.user1, Device.CHANGE_PERMISSION
                )
            ),
            set(self.all_qemu_devices),
        )
        self.assertEqual(
            set(
                Device.objects.all().accessible_by_user(
                    self.user2, Device.CHANGE_PERMISSION
                )
            ),
            set(),
        )
        self.assertEqual(
            set(
                Device.objects.all().accessible_by_user(
                    AnonymousUser(), Device.CHANGE_PERMISSION
                )
            ),
            set(),
        )

        # Now give admin permission for user2 and device3. user2 should be able
        # to admin device3 but user1 should not anymore.
        # Anonymous still cannot admin any devices.
        GroupDevicePermission.objects.assign_perm(
            Device.CHANGE_PERMISSION, self.group2, self.qemu_device3
        )
        self.assertEqual(
            set(
                Device.objects.filter(
                    device_type=self.qemu_device_type
                ).accessible_by_user(self.user1, Device.CHANGE_PERMISSION)
            ),
            {self.qemu_device1, self.qemu_device2},
        )
        self.assertEqual(
            set(
                Device.objects.filter(
                    device_type=self.qemu_device_type
                ).accessible_by_user(self.user2, Device.CHANGE_PERMISSION)
            ),
            {self.qemu_device3},
        )
        self.assertEqual(
            set(
                Device.objects.all().accessible_by_user(
                    AnonymousUser(), Device.CHANGE_PERMISSION
                )
            ),
            set(),
        )

    def test_testjob_manager_view(self):
        # All users see everything before any permissions are assigned.
        self.assertEqual(
            set(TestJob.objects.all().visible_by_user(self.user1)), set(self.all_jobs)
        )
        self.assertEqual(
            set(TestJob.objects.all().visible_by_user(self.user2)), set(self.all_jobs)
        )
        self.assertEqual(
            set(TestJob.objects.all().visible_by_user(AnonymousUser())),
            set(self.all_jobs),
        )

        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.VIEW_PERMISSION, self.group1, self.qemu_device_type
        )

        # user1 should see everything since he has view_permission over
        # qemu_job2 and the other ones are not view restricted
        self.assertEqual(
            set(TestJob.objects.all().visible_by_user(self.user1)), set(self.all_jobs)
        )
        # user2 should see only jobs which are not view restricted.
        self.assertEqual(
            set(TestJob.objects.all().visible_by_user(self.user2)),
            {self.bbb_job1, self.bbb_job2},
        )
        # AnonymousUser can see also see all jobs which are not view
        # restricted.
        self.assertEqual(
            set(TestJob.objects.all().visible_by_user(AnonymousUser())),
            {self.bbb_job1, self.bbb_job2},
        )

    def test_testjob_manager_view_private(self):
        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.VIEW_PERMISSION, self.group1, self.qemu_device_type
        )
        self.qemu_job1.is_public = False
        self.qemu_job1.save()

        self.user1_job = TestJob.from_yaml_and_user(self.definition, self.user1)
        self.user1_job.is_public = False
        self.user1_job.save()

        # user2 should see only jobs which are not view restricted
        # and qemu_job1.
        self.assertEqual(
            set(TestJob.objects.all().visible_by_user(self.user2)),
            {self.bbb_job1, self.bbb_job2},
        )
        # user1 should see user1_job because he's a submitter.
        self.assertEqual(
            set(TestJob.objects.all().visible_by_user(self.user1)),
            {self.qemu_job2, self.bbb_job1, self.bbb_job2, self.user1_job},
        )
        # AnonymousUser can see also see all jobs which are not view
        # restricted and qemu_job1.
        self.assertEqual(
            set(TestJob.objects.all().visible_by_user(AnonymousUser())),
            {self.bbb_job1, self.bbb_job2},
        )

    def test_testjob_manager_viewing_groups(self):
        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.VIEW_PERMISSION, self.group1, self.qemu_device_type
        )
        self.qemu_job1.viewing_groups.add(self.group2)
        self.qemu_job2.viewing_groups.add(self.group1, self.group2)

        # user1 should not see qemu_jobs, despite the permissions allowing him
        # to do so.
        self.assertEqual(
            set(TestJob.objects.all().visible_by_user(self.user1)),
            {self.bbb_job1, self.bbb_job2},
        )
        # user2 should see also qemu_job1 because of viewing_groups field.
        self.assertEqual(
            set(TestJob.objects.all().visible_by_user(self.user2)),
            {self.qemu_job1, self.bbb_job1, self.bbb_job2},
        )
        self.user3.groups.add(self.group1)
        self.user3.groups.add(self.group2)

        # user3 should see all jobs because of viewing_groups field.
        self.assertEqual(
            set(TestJob.objects.all().visible_by_user(self.user3)), set(self.all_jobs)
        )

        # Anon user should see nothing
        # after viewing groups had been set for public jobs
        self.bbb_job1.viewing_groups.add(self.group2)
        self.bbb_job2.viewing_groups.add(self.group1, self.group2)
        self.assertEqual(
            set(TestJob.objects.all().visible_by_user(AnonymousUser())),
            set(),
        )

    def test_testjob_manager_view_through_device_type(self):
        # Restrict the qemu device type. user1 should see all, user2 and
        # anonymous only bbb jobs.
        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.VIEW_PERMISSION, self.group1, self.qemu_device_type
        )
        self.assertEqual(
            set(TestJob.objects.all().visible_by_user(self.user1)), set(self.all_jobs)
        )
        self.assertEqual(
            set(TestJob.objects.all().visible_by_user(self.user2)),
            set(self.all_bbb_jobs),
        )
        self.assertEqual(
            set(TestJob.objects.all().visible_by_user(AnonymousUser())),
            set(self.all_bbb_jobs),
        )

        # Now give view permission for user2 and qemu device 2.
        # user2 should see qemu job2 but user1 should not anymore.
        # Anonymous still does not see anything.
        self.qemu_job1.actual_device = self.qemu_device1
        self.qemu_job1.save()
        self.qemu_job2.actual_device = self.qemu_device2
        self.qemu_job2.save()

        GroupDevicePermission.objects.assign_perm(
            Device.VIEW_PERMISSION, self.group2, self.qemu_device2
        )
        self.assertEqual(
            set(
                TestJob.objects.filter(
                    requested_device_type=self.qemu_device_type
                ).visible_by_user(self.user1)
            ),
            {self.qemu_job1},
        )
        self.assertEqual(
            set(
                TestJob.objects.filter(
                    requested_device_type=self.qemu_device_type
                ).visible_by_user(self.user2)
            ),
            {self.qemu_job2},
        )
        self.assertEqual(
            set(
                TestJob.objects.filter(
                    requested_device_type=self.qemu_device_type
                ).visible_by_user(AnonymousUser())
            ),
            set(),
        )

    def test_testjob_manager_view_through_device(self):
        # Assign testjobs to respective devices (not done by factory).
        self.qemu_job1.actual_device = self.qemu_device1
        self.qemu_job1.save()
        self.qemu_job2.actual_device = self.qemu_device2
        self.qemu_job2.save()

        # Restrict the qemu device 1. user1 should see all, user2 and
        # anonymous only qemu job2 and bbb jobs.
        GroupDevicePermission.objects.assign_perm(
            Device.VIEW_PERMISSION, self.group1, self.qemu_device1
        )
        self.assertEqual(
            set(TestJob.objects.all().visible_by_user(self.user1)), set(self.all_jobs)
        )
        self.assertEqual(
            set(TestJob.objects.all().visible_by_user(self.user2)),
            set(self.all_bbb_jobs).union({self.qemu_job2}),
        )
        self.assertEqual(
            set(TestJob.objects.all().visible_by_user(AnonymousUser())),
            set(self.all_bbb_jobs).union({self.qemu_job2}),
        )

        # Now give view permission for user2 and qemu job 2. user2 should see
        # qemu job2 but user1 should not anymore. Anonymous now sees only bbbs.
        GroupDevicePermission.objects.assign_perm(
            Device.VIEW_PERMISSION, self.group2, self.qemu_device2
        )
        self.assertEqual(
            set(
                TestJob.objects.filter(
                    requested_device_type=self.qemu_device_type
                ).visible_by_user(self.user1)
            ),
            {self.qemu_job1},
        )
        self.assertEqual(
            set(
                TestJob.objects.filter(
                    requested_device_type=self.qemu_device_type
                ).visible_by_user(self.user2)
            ),
            {self.qemu_job2},
        )
        self.assertEqual(
            set(TestJob.objects.all().visible_by_user(AnonymousUser())),
            set(self.all_bbb_jobs),
        )

    def test_testjob_manager_admin(self):
        # auth users can admin none. Same goes for Anonymous
        self.assertEqual(
            set(
                TestJob.objects.all().accessible_by_user(
                    self.user1, TestJob.CHANGE_PERMISSION
                )
            ),
            set(),
        )
        self.assertEqual(
            set(
                TestJob.objects.all().accessible_by_user(
                    AnonymousUser(), TestJob.CHANGE_PERMISSION
                )
            ),
            set(),
        )

        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.CHANGE_PERMISSION, self.group1, self.qemu_device_type
        )
        # user1 should be able to admin only qemu jobs
        self.assertEqual(
            set(
                TestJob.objects.all().accessible_by_user(
                    self.user1, TestJob.CHANGE_PERMISSION
                )
            ),
            {self.qemu_job1, self.qemu_job2},
        )
        # user2 should not be able to admin anything
        self.assertEqual(
            set(
                TestJob.objects.all().accessible_by_user(
                    self.user2, TestJob.CHANGE_PERMISSION
                )
            ),
            set(),
        )
        # AnonymousUser can also still admin over nothing.
        self.assertEqual(
            set(
                TestJob.objects.all().accessible_by_user(
                    AnonymousUser(), TestJob.CHANGE_PERMISSION
                )
            ),
            set(),
        )

    def test_testjob_manager_admin_through_device_type(self):
        # Allow admin on qemu device type to group1 (user1).
        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.CHANGE_PERMISSION, self.group1, self.qemu_device_type
        )

        self.assertEqual(
            set(
                TestJob.objects.all().accessible_by_user(
                    self.user1, TestJob.CHANGE_PERMISSION
                )
            ),
            set(self.all_qemu_jobs),
        )
        self.assertEqual(
            set(
                TestJob.objects.all().accessible_by_user(
                    self.user2, TestJob.CHANGE_PERMISSION
                )
            ),
            set(),
        )
        self.assertEqual(
            set(
                TestJob.objects.all().accessible_by_user(
                    AnonymousUser(), TestJob.CHANGE_PERMISSION
                )
            ),
            set(),
        )

        # Now give admin permission for user2 and qemu device1. user2 should be
        # able to admin qemu jobs but user1 should not anymore.
        # Anonymous still cannot admin any jobs.
        self.qemu_job1.actual_device = self.qemu_device1
        self.qemu_job1.save()
        self.qemu_job2.actual_device = self.qemu_device1
        self.qemu_job2.save()

        GroupDevicePermission.objects.assign_perm(
            Device.CHANGE_PERMISSION, self.group2, self.qemu_device1
        )
        self.assertEqual(
            set(
                TestJob.objects.all().accessible_by_user(
                    self.user1, TestJob.CHANGE_PERMISSION
                )
            ),
            set(),
        )
        self.assertEqual(
            set(
                TestJob.objects.all().accessible_by_user(
                    self.user2, TestJob.CHANGE_PERMISSION
                )
            ),
            {self.qemu_job1, self.qemu_job2},
        )
        self.assertEqual(
            set(
                TestJob.objects.all().accessible_by_user(
                    AnonymousUser(), TestJob.CHANGE_PERMISSION
                )
            ),
            set(),
        )

    def test_testjob_manager_admin_through_device(self):
        # Assign testjobs to respective devices (not done by factory).
        self.qemu_job1.actual_device = self.qemu_device1
        self.qemu_job1.save()
        self.qemu_job2.actual_device = self.qemu_device2
        self.qemu_job2.save()

        # Allow admin on qemu device1 to group1 (user1).
        GroupDevicePermission.objects.assign_perm(
            Device.CHANGE_PERMISSION, self.group1, self.qemu_device1
        )

        self.assertEqual(
            set(
                TestJob.objects.all().accessible_by_user(
                    self.user1, TestJob.CHANGE_PERMISSION
                )
            ),
            {self.qemu_job1},
        )
        self.assertEqual(
            set(
                TestJob.objects.all().accessible_by_user(
                    self.user2, TestJob.CHANGE_PERMISSION
                )
            ),
            set(),
        )
        self.assertEqual(
            set(
                TestJob.objects.all().accessible_by_user(
                    AnonymousUser(), TestJob.CHANGE_PERMISSION
                )
            ),
            set(),
        )

        # Now give admin permission for user2 and qemu device2. user2 should be
        # able to admin qemu job2 but user1 should not anymore.
        # Anonymous still cannot admin any devices.
        GroupDevicePermission.objects.assign_perm(
            Device.CHANGE_PERMISSION, self.group2, self.qemu_device2
        )
        self.assertEqual(
            set(
                TestJob.objects.all().accessible_by_user(
                    self.user1, TestJob.CHANGE_PERMISSION
                )
            ),
            {self.qemu_job1},
        )
        self.assertEqual(
            set(
                TestJob.objects.all().accessible_by_user(
                    self.user2, TestJob.CHANGE_PERMISSION
                )
            ),
            {self.qemu_job2},
        )
        self.assertEqual(
            set(
                TestJob.objects.all().accessible_by_user(
                    AnonymousUser(), TestJob.CHANGE_PERMISSION
                )
            ),
            set(),
        )

    def test_worker_manager_accessible(self):
        GroupWorkerPermission.objects.assign_perm(
            Worker.CHANGE_PERMISSION, self.group1, self.worker1
        )

        # user1 can admin only worker1.
        self.assertEqual(
            set(
                Worker.objects.all().accessible_by_user(
                    self.user1, Worker.CHANGE_PERMISSION
                )
            ),
            {self.worker1},
        )

        # user2 can not admin anything.
        self.assertEqual(
            list(
                Worker.objects.all().accessible_by_user(
                    self.user2, Worker.CHANGE_PERMISSION
                )
            ),
            [],
        )

        # anonymous can not admin anything.
        self.assertEqual(
            list(
                Worker.objects.all().accessible_by_user(
                    AnonymousUser(), Worker.CHANGE_PERMISSION
                )
            ),
            [],
        )

    def test_worker_manager_change_global_permissions(self):
        self.user3.user_permissions.add(
            Permission.objects.get(name="Can change worker")
        )
        GroupWorkerPermission.objects.assign_perm(
            Worker.CHANGE_PERMISSION, self.group1, self.worker2
        )

        # user3 can change all workers based on global permission.
        self.assertEqual(
            set(
                Worker.objects.all().accessible_by_user(
                    self.user3, Worker.CHANGE_PERMISSION
                )
            ),
            set(Worker.objects.all()),
        )

    def test_worker_manager_admin(self):
        # admin user can change all workers.
        self.assertEqual(
            set(
                Worker.objects.all().accessible_by_user(
                    self.admin_user, Worker.CHANGE_PERMISSION
                )
            ),
            set(Worker.objects.all()),
        )

    def test_permissions_duplicate_rows(self):
        # See
        # https://git.lavasoftware.org/lava/lava/-/issues/612
        # https://git.lavasoftware.org/lava/lava/-/merge_requests/2121
        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.VIEW_PERMISSION, self.group1, self.qemu_device_type
        )

        GroupDeviceTypePermission.objects.assign_perm(
            DeviceType.VIEW_PERMISSION, self.group2, self.qemu_device_type
        )

        self.user1.groups.add(self.group2)

        # user1 can view qemu device type through group1 or group2
        # however, only one instance of qemu device type should be returned
        self.assertEqual(
            DeviceType.objects.visible_by_user(self.user1).count(),
            DeviceType.objects.all().count(),
        )
