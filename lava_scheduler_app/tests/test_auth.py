from itertools import chain

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.test import TestCase

from lava_scheduler_app.auth import PermissionAuth
from lava_scheduler_app.models import GroupObjectPermission, TestJob
from lava_scheduler_app.tests.test_submission import TestCaseWithFactory

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
        self.job = TestJob.from_yaml_and_user(self.definition, self.admin_user)

    def tearDown(self):
        super().tearDown()
        GroupObjectPermission.objects.all().delete()

    def test_get_group_perms(self):
        # Test group permission queries.
        auth = PermissionAuth(self.user)
        GroupObjectPermission.objects.assign_perm("admin_testjob", self.group, self.job)
        GroupObjectPermission.objects.assign_perm(
            "admin_device", self.group, self.device
        )
        permissions = auth.get_group_perms(self.job)
        self.assertEqual(
            permissions, {"admin_testjob", "view_testjob", "cancel_resubmit_testjob"}
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
        GroupObjectPermission.objects.assign_perm(
            "view_devicetype", self.group, self.device_type
        )
        self.assertFalse(
            auth.has_perm("lava_scheduler_app.view_devicetype", self.device_type)
        )

    def test_anonymous_restricted_device_type_by_non_view_permission(self):
        guy_fawkes = AnonymousUser()
        auth = PermissionAuth(guy_fawkes)
        GroupObjectPermission.objects.assign_perm(
            "admin_devicetype", self.group, self.device_type
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
        GroupObjectPermission.objects.assign_perm(
            "view_device", self.group, self.device
        )
        self.assertFalse(auth.has_perm("lava_scheduler_app.view_device", self.device))

    def test_anonymous_restricted_device_by_non_view_permission(self):
        guy_fawkes = AnonymousUser()
        auth = PermissionAuth(guy_fawkes)
        GroupObjectPermission.objects.assign_perm(
            "admin_device", self.group, self.device
        )
        self.assertTrue(auth.has_perm("lava_scheduler_app.view_device", self.device))

    def test_anonymous_unrestricted_testjob(self):
        guy_fawkes = AnonymousUser()
        auth = PermissionAuth(guy_fawkes)
        self.assertTrue(auth.has_perm("lava_scheduler_app.view_testjob", self.job))

    def test_anonymous_restricted_testjob(self):
        guy_fawkes = AnonymousUser()
        auth = PermissionAuth(guy_fawkes)
        GroupObjectPermission.objects.assign_perm("view_testjob", self.group, self.job)
        self.assertFalse(auth.has_perm("lava_scheduler_app.view_testjob", self.job))

    def test_anonymous_restricted_testjob_by_non_view_permission(self):
        guy_fawkes = AnonymousUser()
        auth = PermissionAuth(guy_fawkes)
        GroupObjectPermission.objects.assign_perm("admin_testjob", self.group, self.job)
        self.assertTrue(auth.has_perm("lava_scheduler_app.view_testjob", self.job))

    def test_has_perm_unsupported_model(self):
        # Unsupported content_types check will return False.
        user = self.factory.make_user()
        auth = PermissionAuth(user)
        GroupObjectPermission.objects.assign_perm(
            "change_group", self.group, self.group
        )
        self.assertFalse(auth.has_perm("auth.change_group", self.group))

    def test_superuser(self):
        user = User.objects.create(username="superuser", is_superuser=True)
        auth = PermissionAuth(user)
        content_type = ContentType.objects.get_for_model(self.job)
        perms = set(
            chain(
                *Permission.objects.filter(content_type=content_type).values_list(
                    "codename"
                )
            )
        )
        self.assertEqual(perms, auth.get_perms(self.job))
        for perm in perms:
            self.assertTrue(
                auth.has_perm("%s.%s" % (content_type.app_label, perm), self.job)
            )

    def test_not_active_superuser(self):
        user = User.objects.create(
            username="not_active_superuser", is_superuser=True, is_active=False
        )
        check = PermissionAuth(user)
        content_type = ContentType.objects.get_for_model(self.job)
        perms = sorted(
            chain(
                *Permission.objects.filter(content_type=content_type).values_list(
                    "codename"
                )
            )
        )
        self.assertEqual(check.get_perms(self.job), [])
        for perm in perms:
            self.assertFalse(
                check.has_perm("%s.%s" % (content_type.app_label, perm), self.job)
            )

    def test_not_active_user(self):
        user = User.objects.create(username="notactive")
        user.groups.add(self.group)
        GroupObjectPermission.objects.assign_perm("admin_testjob", self.group, self.job)

        check = PermissionAuth(user)
        self.assertTrue(check.has_perm("lava_scheduler_app.admin_testjob", self.job))
        user.is_active = False
        self.assertFalse(check.has_perm("lava_scheduler_app.admin_testjob", self.job))

        user = User.objects.create(username="notactive-cache")
        user.groups.add(self.group)
        GroupObjectPermission.objects.assign_perm("admin_testjob", self.group, self.job)

        check = PermissionAuth(user)
        self.assertTrue(check.has_perm("lava_scheduler_app.admin_testjob", self.job))
        user.is_active = False
        self.assertFalse(check.has_perm("lava_scheduler_app.admin_testjob", self.job))

    def test_get_perms(self):
        device1 = self.factory.make_device(
            device_type=self.device_type, hostname="qemu-test-1"
        )
        job1 = TestJob.from_yaml_and_user(self.definition, self.admin_user)
        job2 = TestJob.from_yaml_and_user(self.definition, self.admin_user)

        assign_perms = {
            device1: ("view_device",),
            job1: ("admin_testjob",),
            job2: ("cancel_resubmit_testjob",),
        }

        auth = PermissionAuth(self.user)

        for obj, perms in assign_perms.items():
            for perm in perms:
                GroupObjectPermission.objects.assign_perm(perm, self.group, obj)
            self.assertTrue(set(perms).issubset(auth.get_perms(obj)))

    def test_prefetch_user_perms(self):
        settings.DEBUG = True
        try:
            from django.db import connection

            ContentType.objects.clear_cache()
            job1 = TestJob.from_yaml_and_user(self.definition, self.admin_user)
            job2 = TestJob.from_yaml_and_user(self.definition, self.admin_user)
            group = self.factory.make_group(name="group")

            user = User.objects.create(username="test_active_user", is_active=True)
            user.groups.add(group)

            GroupObjectPermission.objects.assign_perm("admin_testjob", group, job1)
            GroupObjectPermission.objects.assign_perm("admin_testjob", group, job2)
            auth = PermissionAuth(user)

            prefetched_objects = TestJob.objects.filter(id__in=[job1.id, job2.id])
            self.assertTrue(auth.prefetch_perms(prefetched_objects))
            query_count = len(connection.queries)

            # Checking cache is filled
            self.assertEqual(len(auth._cache), len(prefetched_objects))

            # Permission check shouldn't spawn any queries
            self.assertTrue(auth.has_perm("lava_scheduler_app.admin_testjob", job1))
            self.assertEqual(len(connection.queries), query_count)

            # Check for other permission with same object shouldn't spawn any
            # queries as well
            auth.has_perm("lava_scheduler_app.admin_testjob", job1)
            self.assertEqual(len(connection.queries), query_count)

            # Check for same model but other object shouldn't spawn any
            # queries
            self.assertTrue(auth.has_perm("lava_scheduler_app.admin_testjob", job2))
            self.assertEqual(len(connection.queries), query_count)

            # Check for same model but other object shouldn't spawn
            # any queries. Even though user doesn't have perms on job2, we
            # still should not hit DB.
            auth.has_perm("lava_scheduler_app.admin_testjob", job2)
            self.assertEqual(len(connection.queries), query_count)
        finally:
            settings.DEBUG = False

    def test_cache_for_queries_count(self):
        settings.DEBUG = True
        try:
            from django.db import connection

            ContentType.objects.clear_cache()
            auth = PermissionAuth(self.user)

            query_count = len(connection.queries)
            res = auth.has_perm("lava_scheduler_app.admin_device", self.device)
            expected = 2
            self.assertEqual(len(connection.queries), query_count + expected)

            # Another check shouldn't spawn any queries
            query_count = len(connection.queries)
            res_new = auth.has_perm("lava_scheduler_app.admin_device", self.device)
            self.assertEqual(res, res_new)
            self.assertEqual(len(connection.queries), query_count)

            # Check for same model but other object shouldn't spawn any
            # queries
            auth.has_perm("lava_scheduler_app.submit_to_device", self.device)
            self.assertEqual(len(connection.queries), query_count)

            # Checking for same model but other instance should spawn 1 query
            new_device = self.factory.make_device(
                device_type=self.device_type, hostname="qemu-11"
            )
            query_count = len(connection.queries)
            auth.has_perm("lava_scheduler_app.view_device", new_device)
            self.assertEqual(len(connection.queries), query_count + 1)

            # Checking for permission for other model should spawn 2 queries
            # every added direct relation adds one more query..
            query_count = len(connection.queries)
            auth.has_perm("lava_scheduler_app.admin_testjob", self.job)
            self.assertEqual(len(connection.queries), query_count + 2)
        finally:
            settings.DEBUG = False

    def test_filter_queryset_by_perms_non_allowed_permission(self):
        auth = PermissionAuth(self.user)
        # Cannot use device permissions with TestJob content_type.
        with TestCase.assertRaises(self, ValueError):
            auth.filter_queryset_by_perms(
                ["lava_scheduler_app.submit_to_device"], TestJob.objects.all()
            )

    def test_filter_queryset_by_perms_non_existing_permission(self):
        auth = PermissionAuth(self.user)
        # Cannot use non existing permissions.
        with TestCase.assertRaises(self, ValueError):
            auth.filter_queryset_by_perms(
                ["lava_scheduler_app.wrong_permission_name"], TestJob.objects.all()
            )

    def test_filter_queryset_by_perms_match_any_single_group(self):
        settings.DEBUG = True
        try:
            from django.db import connection

            ContentType.objects.clear_cache()

            auth = PermissionAuth(self.user)

            job1 = TestJob.from_yaml_and_user(self.definition, self.admin_user)
            job2 = TestJob.from_yaml_and_user(self.definition, self.admin_user)
            job3 = TestJob.from_yaml_and_user(self.definition, self.admin_user)
            testjobs = TestJob.objects.filter(id__in=[job1.id, job2.id, job3.id])

            GroupObjectPermission.objects.assign_perm("admin_testjob", self.group, job1)
            GroupObjectPermission.objects.assign_perm(
                "cancel_resubmit_testjob", self.group, job2
            )

            queryset = testjobs.filter(
                Q(
                    pk__in=auth.filter_queryset_by_perms(
                        ["lava_scheduler_app.cancel_resubmit_testjob"], testjobs
                    )
                )
            )
            self.assertEqual(list(queryset), [job1, job2])

            queryset = testjobs.filter(
                Q(
                    pk__in=auth.filter_queryset_by_perms(
                        ["lava_scheduler_app.admin_testjob"], testjobs
                    )
                )
            )
            self.assertEqual(list(queryset), [job1])

            queryset = testjobs.filter(
                Q(
                    pk__in=auth.filter_queryset_by_perms(
                        ["lava_scheduler_app.view_testjob"], testjobs
                    )
                )
            )
            self.assertEqual(list(queryset), [job1, job2])

            queryset = testjobs.filter(
                Q(
                    pk__in=auth.filter_queryset_by_perms(
                        [
                            "lava_scheduler_app.cancel_resubmit_testjob",
                            "lava_scheduler_app.admin_testjob",
                        ],
                        testjobs,
                    )
                )
            )
            self.assertEqual(list(queryset), [job1, job2])

            GroupObjectPermission.objects.assign_perm(
                "cancel_resubmit_testjob", self.group, job1
            )
            query_count = len(connection.queries)

            queryset = auth.filter_queryset_by_perms(
                ["lava_scheduler_app.cancel_resubmit_testjob"], testjobs
            )
            self.assertEqual(set(queryset), {str(job1.pk), str(job2.pk)})
            self.assertEqual(len(connection.queries), query_count + 3)
        finally:
            settings.DEBUG = False

    def test_filter_queryset_by_perms_match_any_multiple_groups(self):
        group1 = self.factory.make_group(name="test_group1")
        group2 = self.factory.make_group(name="test_group2")
        user1 = self.factory.make_user()
        user1.groups.add(group1)
        user1.groups.add(group2)

        auth = PermissionAuth(user1)

        job1 = TestJob.from_yaml_and_user(self.definition, self.admin_user)
        job2 = TestJob.from_yaml_and_user(self.definition, self.admin_user)
        job3 = TestJob.from_yaml_and_user(self.definition, self.admin_user)
        testjobs = TestJob.objects.filter(id__in=[job1.id, job2.id, job3.id])

        GroupObjectPermission.objects.assign_perm("admin_testjob", group1, job1)
        GroupObjectPermission.objects.assign_perm(
            "cancel_resubmit_testjob", group2, job2
        )

        queryset = testjobs.filter(
            Q(
                pk__in=auth.filter_queryset_by_perms(
                    ["lava_scheduler_app.cancel_resubmit_testjob"], testjobs
                )
            )
        )
        self.assertEqual(list(queryset), [job1, job2])

        queryset = testjobs.filter(
            Q(
                pk__in=auth.filter_queryset_by_perms(
                    ["lava_scheduler_app.admin_testjob"], testjobs
                )
            )
        )
        self.assertEqual(list(queryset), [job1])

        queryset = testjobs.filter(
            Q(
                pk__in=auth.filter_queryset_by_perms(
                    ["lava_scheduler_app.view_testjob"], testjobs
                )
            )
        )
        self.assertEqual(list(queryset), [job1, job2])

        queryset = testjobs.filter(
            Q(
                pk__in=auth.filter_queryset_by_perms(
                    [
                        "lava_scheduler_app.cancel_resubmit_testjob",
                        "lava_scheduler_app.admin_testjob",
                    ],
                    testjobs,
                )
            )
        )
        self.assertEqual(list(queryset), [job1, job2])

        GroupObjectPermission.objects.assign_perm(
            "cancel_resubmit_testjob", group2, job1
        )
        queryset = testjobs.filter(
            Q(
                pk__in=auth.filter_queryset_by_perms(
                    ["lava_scheduler_app.cancel_resubmit_testjob"], testjobs
                )
            )
        )
        self.assertEqual(list(queryset), [job1, job2])

    def test_filter_queryset_by_perms_match_all(self):

        auth = PermissionAuth(self.user)

        job1 = TestJob.from_yaml_and_user(self.definition, self.admin_user)
        job2 = TestJob.from_yaml_and_user(self.definition, self.admin_user)
        testjobs = TestJob.objects.filter(id__in=[job1.id, job2.id])

        GroupObjectPermission.objects.assign_perm(
            "cancel_resubmit_testjob", self.group, job1
        )
        GroupObjectPermission.objects.assign_perm(
            "cancel_resubmit_testjob", self.group, job2
        )
        GroupObjectPermission.objects.assign_perm("admin_testjob", self.group, job2)

        queryset = testjobs.filter(
            Q(
                pk__in=auth.filter_queryset_by_perms(
                    [
                        "lava_scheduler_app.cancel_resubmit_testjob",
                        "lava_scheduler_app.admin_testjob",
                    ],
                    testjobs,
                    match_all=True,
                )
            )
        )
        self.assertEqual(list(queryset), [job2])

    def test_filter_queryset_by_perms_superuser(self):

        user = User.objects.create(username="another_superuser", is_superuser=True)
        auth = PermissionAuth(user)

        job1 = TestJob.from_yaml_and_user(self.definition, self.admin_user)
        job2 = TestJob.from_yaml_and_user(self.definition, self.admin_user)
        testjobs = TestJob.objects.filter(id__in=[job1.id, job2.id])

        queryset = testjobs.filter(
            Q(
                pk__in=auth.filter_queryset_by_perms(
                    ["lava_scheduler_app.cancel_resubmit_testjob"],
                    testjobs,
                    match_all=True,
                )
            )
        )
        self.assertEqual(list(queryset), [job1, job2])

        queryset = testjobs.filter(
            Q(
                pk__in=auth.filter_queryset_by_perms(
                    ["lava_scheduler_app.admin_testjob"], testjobs, match_all=True
                )
            )
        )
        self.assertEqual(list(queryset), [job1, job2])

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
