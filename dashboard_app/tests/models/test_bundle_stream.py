# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Lava Dashboard.
#
# Lava Dashboard is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Lava Dashboard is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Lava Dashboard.  If not, see <http://www.gnu.org/licenses/>.

"""
Tests for the BundleStream model
"""

from django.contrib.auth.models import User, Group
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django_testscenarios.ubertest import TestCase, TestCaseWithScenarios

from dashboard_app.models import BundleStream
from dashboard_app.tests import fixtures


class BundleStreamTests(TestCaseWithScenarios):

    _NAME = "name"
    _SLUG = "slug"
    _GROUPNAME = "group"
    _USERNAME = "user"

    scenarios = [
        ('anonymous-no-slug', {
            'pathname': '/anonymous/',
            'is_public': True,
            'is_anonymous': True,
            'username': "user",
        }),
        ('anonymous-with-slug', {
            'name': _NAME,
            'slug': _SLUG,
            'is_public': True,
            'is_anonymous': True,
            'pathname': '/anonymous/slug/',
            'username': "user",
        }),
        ('personal-no-slug', {
            'username': _USERNAME,
            'pathname': '/private/personal/user/',
        }),
        ('personal-with-slug', {
            'username': _USERNAME,
            'name': _NAME,
            'slug': _SLUG,
            'pathname': '/private/personal/user/slug/',
        }),
        ('team-no-slug', {
            'groupname': _GROUPNAME,
            'pathname': '/private/team/group/',
        }),
        ('team-with-slug', {
            'groupname': _GROUPNAME,
            'name': _NAME,
            'slug': _SLUG,
            'pathname': '/private/team/group/slug/',
        }),
    ]

    groupname = None
    username = None
    group = None
    user = None
    name = ''
    slug = ''
    is_public = 0
    is_anonymous = 0

    def setUp(self):
        super(BundleStreamTests, self).setUp()
        if self.username is not None:
            self.user = User.objects.create(username='user')
        if self.groupname is not None:
            self.group = Group.objects.create(name='group')

    def test_creation(self):
        bundle_stream = BundleStream.objects.create(
            user=self.user,
            group=self.group,
            name=self.name,
            is_anonymous=False,
            is_public=False,
            slug=self.slug)
        bundle_stream.save()
        self.assertEqual(bundle_stream.user, self.user)
        self.assertEqual(bundle_stream.group, self.group)
        self.assertEqual(bundle_stream.name, self.name)
        self.assertEqual(bundle_stream.slug, self.slug)

    def test_team_named_stream(self):
        bundle_stream = BundleStream.objects.create(
            user=self.user, group=self.group, name=self.name, slug=self.slug,
            is_anonymous=self.is_anonymous, is_public=self.is_public)
        bundle_stream.save()
        self.assertEqual(bundle_stream.pathname, self.pathname)

    def test_pathname_uniqueness(self):
        bundle_stream = BundleStream.objects.create(
            user=self.user,
            group=self.group,
            name=self.name,
            is_anonymous=False,
            is_public=False,
            slug=self.slug)
        bundle_stream.save()
        self.assertRaises(
            IntegrityError,
            BundleStream.objects.create,
            user=self.user, group=self.group, slug=self.slug,
            name=self.name
        )

    def test_pathname_update(self):
        bundle_stream = BundleStream.objects.create(
            user=self.user,
            group=self.group,
            name=self.name,
            is_anonymous=False,
            is_public=False,
            slug=self.slug)
        bundle_stream.save()
        old_pathname = bundle_stream.pathname
        bundle_stream.slug += "-changed"
        bundle_stream.save()
        self.assertNotEqual(bundle_stream.pathname, old_pathname)
        self.assertEqual(
            bundle_stream.pathname,
            bundle_stream._calc_pathname()
        )

    def test_unicode(self):
        obj = BundleStream(pathname=self.pathname)
        self.assertEqual(unicode(obj), self.pathname)


class BundleStreamPermissionTests(TestCase):

    def test_can_upload_to_anonymous(self):
        user = User.objects.create(username='user')
        bundle_stream = fixtures.create_bundle_stream("/anonymous/")
        self.assertTrue(bundle_stream.can_upload(user))


class BundleStreamUploadPermissionTests(TestCase):

    def test_can_upload_to_owned_stream(self):
        bundle_stream = fixtures.create_bundle_stream("/public/personal/owner/")
        user = User.objects.get(username='owner')
        self.assertTrue(bundle_stream.can_upload(user))

    def test_can_upload_to_other_stream(self):
        bundle_stream = fixtures.create_bundle_stream("/public/personal/owner/")
        user = User.objects.create(username='non-owner')
        self.assertFalse(bundle_stream.can_upload(user))
        user.delete()


class BundleStreamPermissionOwnedTests(TestCase):

    def test_group_can_upload_to_owned(self):
        group = Group.objects.create(name='group')
        member = User.objects.create(username="member")
        group.user_set.add(member)
        other = User.objects.create(username="other")
        bundle_stream = fixtures.create_bundle_stream("/public/team/group/basic/")
        self.assertTrue(bundle_stream.can_upload(member))
        self.assertFalse(bundle_stream.can_upload(other))


class BundleStreamPermissionDeniedTests(TestCase):

    def test_create_from_pathname_permission_denied_user(self):
        user = User.objects.get_or_create(username="non-owner")[0]
        self.assertRaises(
            PermissionDenied,
            BundleStream.create_from_pathname,
            "/private/personal/owner/name/", user)


class BundleStreamGroupPermissionTests(TestCase):

    def test_create_from_pathname_permission_denied_group(self):
        user = User.objects.create(username="non-owner")
        self.assertRaises(
            PermissionDenied,
            BundleStream.create_from_pathname,
            "/public/team/group/name/", user)
        user.delete()


class BundleStreamAnonymousPermissionTests(TestCase):

    def test_create_from_pathname_permission_denied_anonymous(self):
        self.assertRaises(
            PermissionDenied,
            BundleStream.create_from_pathname,
            "/public/team/group/name/", user=None)


class BundleStreamPathnameTests(TestCase):

    def test_create_from_pathname(self):
        user = User.objects.get_or_create(username="owner")[0]
        bundle_stream = BundleStream.create_from_pathname(
            "/private/personal/owner/name/", user)
        self.assertEqual(bundle_stream.pathname,
                         "/private/personal/owner/name/")
        group = Group.objects.create(name='group')
        group.user_set.add(user)
        bundle_stream = BundleStream.create_from_pathname(
            "/private/team/group/name/", user)
        self.assertEqual(bundle_stream.pathname, "/private/team/group/name/")
        bundle_stream = BundleStream.create_from_pathname(
            "/anonymous/name/", user=None)
        self.assertEqual(bundle_stream.pathname, "/anonymous/name/")
        group.delete()


class BundleStreamIntegrityTests(TestCase):

    def test_create_from_pathname_permission_denied_integrity(self):
        BundleStream.objects.all().delete()
        BundleStream.create_from_pathname("/anonymous/name/", user=None)
        self.assertRaises(
            IntegrityError,
            BundleStream.create_from_pathname,
            "/anonymous/name/", user=None)
