# Copyright (C) 2019 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


from itertools import chain

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from lava_common.exceptions import PermissionNameError
from lava_scheduler_app.auth import PermissionAuth
from lava_scheduler_app.models import (
    GroupDevicePermission,
    GroupDeviceTypePermission,
    GroupObjectPermission,
)
from tests.lava_scheduler_app.test_submission import TestCaseWithFactory

User = get_user_model()


class PermissionAuthTest(TestCaseWithFactory):
    def setUp(self):
        super().setUp()
        self.admin_user = User.objects.create(
            username=self.factory.get_unique_user(), is_superuser=True
        )

        self.group = self.factory.make_group(name="group1")
        self.user = self.factory.make_user()
        self.user.groups.add(self.group)

        self.definition = self.factory.make_job_data_from_file(
            "qemu-pipeline-first-job.yaml"
        )
        self.device_type = self.factory.make_device_type(name="qemu")
        self.device = self.factory.make_device(
            device_type=self.device_type, hostname="qemu-1"
        )

    def tearDown(self):
        super().tearDown()
        GroupDeviceTypePermission.objects.all().delete()
        GroupDevicePermission.objects.all().delete()

    def test_get_group_perms(self):
        # Test group permission queries.
        auth = PermissionAuth(self.user)
        GroupDevicePermission.objects.assign_perm(
            "change_device", self.group, self.device
        )
        permissions = auth.get_group_perms(self.device)
        self.assertEqual(
            permissions, {"change_device", "view_device", "submit_to_device"}
        )

    def test_anonymous_unrestricted_device_type(self):
        guy_fawkes = AnonymousUser()
        auth = PermissionAuth(guy_fawkes)
        self.assertTrue(
            auth.has_perm("lava_scheduler_app.view_devicetype", self.device_type)
        )

    def test_anonymous_restricted_device_type(self):
        guy_fawkes = AnonymousUser()
        auth = PermissionAuth(guy_fawkes)
        GroupDeviceTypePermission.objects.assign_perm(
            "view_devicetype", self.group, self.device_type
        )
        self.assertFalse(
            auth.has_perm("lava_scheduler_app.view_devicetype", self.device_type)
        )

    def test_anonymous_restricted_device_type_by_non_view_permission(self):
        guy_fawkes = AnonymousUser()
        auth = PermissionAuth(guy_fawkes)
        GroupDeviceTypePermission.objects.assign_perm(
            "change_devicetype", self.group, self.device_type
        )
        self.assertTrue(
            auth.has_perm("lava_scheduler_app.view_devicetype", self.device_type)
        )

    def test_anonymous_unrestricted_device(self):
        guy_fawkes = AnonymousUser()
        auth = PermissionAuth(guy_fawkes)
        self.assertTrue(auth.has_perm("lava_scheduler_app.view_device", self.device))

    def test_anonymous_restricted_device(self):
        guy_fawkes = AnonymousUser()
        auth = PermissionAuth(guy_fawkes)
        GroupDevicePermission.objects.assign_perm(
            "view_device", self.group, self.device
        )
        self.assertFalse(auth.has_perm("lava_scheduler_app.view_device", self.device))

    def test_anonymous_restricted_device_by_non_view_permission(self):
        guy_fawkes = AnonymousUser()
        auth = PermissionAuth(guy_fawkes)
        GroupDevicePermission.objects.assign_perm(
            "change_device", self.group, self.device
        )
        self.assertTrue(auth.has_perm("lava_scheduler_app.view_device", self.device))

    def test_has_perm_unsupported_model(self):
        # Unsupported permission codename will raise PermissionNameError.
        user = self.factory.make_user()
        auth = PermissionAuth(user)
        with TestCase.assertRaises(self, PermissionNameError):
            GroupDevicePermission.objects.assign_perm(
                "change_group", self.group, self.device
            )

    def test_superuser(self):
        user = User.objects.create(username="superuser", is_superuser=True)
        auth = PermissionAuth(user)
        content_type = ContentType.objects.get_for_model(self.device)
        perms = set(
            chain(
                *Permission.objects.filter(content_type=content_type).values_list(
                    "codename"
                )
            )
        )
        self.assertEqual(perms, auth.get_perms(self.device))
        for perm in perms:
            self.assertTrue(
                auth.has_perm("%s.%s" % (content_type.app_label, perm), self.device)
            )

    def test_not_active_superuser(self):
        user = User.objects.create(
            username="not_active_superuser", is_superuser=True, is_active=False
        )
        check = PermissionAuth(user)
        content_type = ContentType.objects.get_for_model(self.device)
        perms = sorted(
            chain(
                *Permission.objects.filter(content_type=content_type).values_list(
                    "codename"
                )
            )
        )
        self.assertEqual(check.get_perms(self.device), [])
        for perm in perms:
            self.assertFalse(
                check.has_perm("%s.%s" % (content_type.app_label, perm), self.device)
            )

    def test_not_active_user(self):
        user = User.objects.create(username="notactive")
        user.groups.add(self.group)
        GroupDevicePermission.objects.assign_perm(
            "change_device", self.group, self.device
        )

        check = PermissionAuth(user)
        self.assertTrue(check.has_perm("lava_scheduler_app.change_device", self.device))
        user.is_active = False
        self.assertFalse(
            check.has_perm("lava_scheduler_app.change_device", self.device)
        )

    def test_get_perms(self):
        device1 = self.factory.make_device(
            device_type=self.device_type, hostname="qemu-tmp-01"
        )
        device2 = self.factory.make_device(
            device_type=self.device_type, hostname="qemu-tmp-02"
        )

        assign_perms = {device1: ("change_device",), device2: ("view_device",)}

        auth = PermissionAuth(self.user)

        for obj, perms in assign_perms.items():
            for perm in perms:
                GroupDevicePermission.objects.assign_perm(perm, self.group, obj)
            self.assertTrue(set(perms).issubset(auth.get_perms(obj)))

    def test_ensure_users_group_has_associated_groups(self):
        test_user = self.factory.make_user()
        unwanted_group = self.factory.make_group(name="unwanted_group")
        test_user.groups.add(unwanted_group)
        group = GroupObjectPermission.ensure_users_group(test_user)
        # Ensure that groups are not removed for this user.
        self.assertEqual(test_user.groups.count(), 2)
        # Test that our new group has correct name and
        # only this user associated.
        self.assertEqual(group.name, test_user.username)
        self.assertEqual(group.user_set.count(), 1)

    def test_ensure_users_group_has_associated_users(self):
        test_user = self.factory.make_user()
        unwanted_user = self.factory.make_user()
        users_group = self.factory.make_group(name=test_user.username)
        users_group.user_set.add(unwanted_user)
        GroupObjectPermission.ensure_users_group(test_user)
        self.assertEqual(test_user.groups.count(), 1)
        self.assertEqual(test_user.groups.first().name, test_user.username)
        self.assertEqual(test_user.groups.first().user_set.count(), 1)

    def test_ensure_users_group(self):
        test_user = self.factory.make_user()
        group = GroupObjectPermission.ensure_users_group(test_user)
        self.assertEqual(test_user.groups.count(), 1)
        self.assertEqual(group.name, test_user.username)
