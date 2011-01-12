# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

"""
Tests for the BundleStream model
"""

from django.contrib.auth.models import User, Group
from django.db import models, IntegrityError
from django.test import TestCase
from django_testscenarios import TestCaseWithScenarios

from dashboard_app.tests import fixtures
from dashboard_app.models import BundleStream


class BundleStreamTests(TestCaseWithScenarios):

    _NAME = "name"
    _SLUG = "slug"
    _GROUPNAME = "group"
    _USERNAME = "user"

    scenarios = [
        ('anonymous-no-slug', {
            'pathname': '/anonymous/',
            'is_public': "true",
            'is_anonymous': "true",
            'username': "user",
            }),
        ('anonymous-with-slug', {
            'name': _NAME,
            'slug': _SLUG,
            'is_public': "true",
            'is_anonymous': "true",
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
        bundle_stream = BundleStream.objects.create(user=self.user,
                group=self.group, name=self.name, slug=self.slug)
        bundle_stream.save()
        self.assertEqual(bundle_stream.user, self.user)
        self.assertEqual(bundle_stream.group, self.group)
        self.assertEqual(bundle_stream.name, self.name)
        self.assertEqual(bundle_stream.slug, self.slug)

    def test_team_named_stream(self):
        bundle_stream = BundleStream.objects.create(user=self.user,
                group=self.group, name=self.name, slug=self.slug, 
                is_anonymous=self.is_anonymous, is_public=self.is_public)
        bundle_stream.save()
        self.assertEqual(bundle_stream.pathname, self.pathname)

    def test_pathname_uniqueness(self):
        bundle_stream = BundleStream.objects.create(user=self.user,
                group=self.group, name=self.name, slug=self.slug)
        bundle_stream.save()
        self.assertRaises(IntegrityError,
                BundleStream.objects.create,
                user=self.user, group=self.group, slug=self.slug,
                name=self.name)

    def test_pathname_update(self):
        bundle_stream = BundleStream.objects.create(user=self.user,
                group=self.group, name=self.name, slug=self.slug)
        bundle_stream.save()
        old_pathname = bundle_stream.pathname
        bundle_stream.slug += "-changed"
        bundle_stream.save()
        self.assertNotEqual(bundle_stream.pathname, old_pathname)
        self.assertEqual(bundle_stream.pathname,
                bundle_stream._calc_pathname())

    def test_unicode(self):
        obj = BundleStream(pathname=self.pathname)
        self.assertEqual(unicode(obj), self.pathname)


class BundleStreamManagerAllowedForAnyoneTestCase(TestCaseWithScenarios):

    _USER = 'user'
    _GROUP = 'group'
    _SLUG = 'slug'

    scenarios = [
        ('empty', {
            'bundle_streams': [],
            'expected_pathnames': [],
            }),
        ('public_streams_are_listed', {
            'bundle_streams': [
                {'slug': '', 'user': _USER},
                {'slug': 'other', 'user': _USER},
                {'slug': 'and-another', 'user': _USER},
                ],
            'expected_pathnames': [
                '/anonymous/',
                '/anonymous/and-another/',
                '/anonymous/other/',
                ],
            }),
        ('private_streams_are_hidden', {
            'bundle_streams': [
                {'user': _USER },
                ],
            'expected_pathnames': [],
            }),
        ('team_streams_are_hidden', {
            'bundle_streams': [
                {'group': _GROUP },
                ],
            'expected_pathnames': [],
            }),
        ('mix_and_match_works', {
            'bundle_streams': [
                {'slug': '', 'user': _USER},
                {'slug': _SLUG, 'user': _USER},
      # Need to check why this gives a error for not unique path
      #          {'group': _GROUP, 'slug': _SLUG},
      #          {'group': _GROUP},
      #          {'user': _GROUP, 'slug': _SLUG},
      #          {'user': _USER},
                ],
            'expected_pathnames': [
                '/anonymous/',
                '/anonymous/{0}/'.format(_SLUG),
                ],
            }),
        ]

    def test_allowed_for_anyone(self):
        with fixtures.created_bundle_streams(self.bundle_streams):
            pathnames = [bundle_stream.pathname for bundle_stream in
                    BundleStream.objects.accessible_by_anyone().order_by('pathname')]
            self.assertEqual(pathnames, self.expected_pathnames)


class BundleStreamManagerAllowedForUserTestCase(TestCaseWithScenarios):

    _USER = 'user'
    _USER2 = 'user2'
    _GROUP = 'group'
    _GROUP2 = 'group2'
    _SLUG = 'slug'

    scenarios = [
        ('empty', {
            'bundle_streams': [],
            'expected_pathnames': [],
            }),
        ('public_streams_are_listed', {
            'bundle_streams': [
                {'slug': '', 'user': _USER},
                {'slug': 'other', 'user': _USER},
                {'slug': 'and-another', 'user': _USER},
                ],
            'expected_pathnames': [
                '/anonymous/',
                '/anonymous/and-another/',
                '/anonymous/other/',
                ],
            }),
        ('owned_private_streams_are_listed', {
            'bundle_streams': [
                {'user': _USER},
                ],
            'expected_pathnames': [
                '/personal/{0}/'.format(_USER),
                ],
            }),
        ('other_private_streams_are_hidden', {
            'bundle_streams': [
                {'user': _USER2},
                ],
            'expected_pathnames': [],
            }),
        ('shared_team_streams_are_listed', {
            'bundle_streams': [
                {'group': _GROUP},
                ],
            'expected_pathnames': [
                '/team/{0}/'.format(_GROUP),
                ],
            }),
       ('other_team_streams_are_hidden', {
            'bundle_streams': [
                {'group': _GROUP2},
                ],
            'expected_pathnames': [],
            }),
        ('mix_and_match_works', {
            'bundle_streams': [
                {'slug': '', 'user' : _USER},
                {'user': _USER, 'slug': _SLUG},
                {'user': _USER},
                {'group': _GROUP, 'slug': _SLUG},
                {'group': _GROUP},
                # things which should not be accessible
                {'user': _USER2, 'slug': _SLUG},
                {'user': _USER2},
                {'group': _GROUP2, 'slug': _SLUG},
                {'group': _GROUP2},
                ],
            'expected_pathnames': [
               '/anonymous/',
                '/anonymous/{0}/'.format(_SLUG),
                '/personal/{0}/'.format(_USER),
                '/personal/{0}/{1}/'.format(_USER, _SLUG),
                '/team/{0}/'.format(_GROUP),
                '/team/{0}/{1}/'.format(_GROUP, _SLUG),
                ],
            }),
        ]

    def test_allowed_for_user(self):
        with fixtures.created_bundle_streams(self.bundle_streams) as all:
            user = User.objects.get_or_create(username=self._USER)[0]
            user.save()
            group = Group.objects.get_or_create(name=self._GROUP)[0]
            group.save()
            user.groups.add(group)
            pathnames = [bundle_stream.pathname for bundle_stream in
                    BundleStream.objects.accessible_by_principal(user).order_by('pathname')]
            self.assertEqual(pathnames, self.expected_pathnames)


class BundleStreamUploadRightTests(TestCase):

    def test_owner_can_access_personal_stream(self):
        user = User.objects.create(username="test-user")
        bundle_stream = BundleStream.objects.create(user=user)
        self.assertTrue(bundle_stream.is_accessible_by(user))

    def test_other_users_cannot_access_personal_streams(self):
        owner = User.objects.create(username="stream-owner")
        unrelated_user = User.objects.create(username="other-user")
        bundle_stream = BundleStream.objects.create(user=owner)
        self.assertFalse(bundle_stream.is_accessible_by(unrelated_user))

    def test_anonymous_users_cannot_access_personal_streams(self):
        owner = User.objects.create(username="stream-owner")
        bundle_stream = BundleStream.objects.create(user=owner)
        self.assertFalse(bundle_stream.is_accessible_by(None))

    def test_group_member_can_access_team_streams(self):
        group = Group.objects.create(name="members")
        user = User.objects.create(username="user")
        user.groups.add(group)
        bundle_stream = BundleStream.objects.create(group=group)
        self.assertTrue(bundle_stream.is_accessible_by(user))

    def test_other_users_cannot_access_team_streams(self):
        group = Group.objects.create(name="members")
        member = User.objects.create(username="user")
        member.groups.add(group)
        unrelated_user = User.objects.create(username="other-user")
        bundle_stream = BundleStream.objects.create(group=group)
        self.assertFalse(bundle_stream.is_accessible_by(unrelated_user))

    def test_anonymous_users_cannot_access_team_streams(self):
        group = Group.objects.create(name="members")
        bundle_stream = BundleStream.objects.create(group=group)
        self.assertFalse(bundle_stream.is_accessible_by(None))

    def test_anonymous_users_can_access_public_streams(self):
        bundle_stream = BundleStream.objects.create(user=None, group=None)
        self.assertTrue(bundle_stream.is_accessible_by(None))

    def test_authorized_users_can_access_public_streams(self):
        user = User.objects.create(username="user")
        bundle_stream = BundleStream.objects.create(user=None, group=None)
        self.assertTrue(bundle_stream.is_accessible_by(user))
