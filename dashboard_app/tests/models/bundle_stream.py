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
from django.db import IntegrityError
from django_testscenarios.ubertest import TestCaseWithScenarios

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
        bundle_stream = BundleStream.objects.create(
            user=self.user, group=self.group, name=self.name, slug=self.slug)
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
            user=self.user, group=self.group, name=self.name, slug=self.slug)
        bundle_stream.save()
        self.assertRaises(
            IntegrityError,
            BundleStream.objects.create,
            user=self.user, group=self.group, slug=self.slug,
            name=self.name
        )

    def test_pathname_update(self):
        bundle_stream = BundleStream.objects.create(
            user=self.user, group=self.group, name=self.name, slug=self.slug)
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
