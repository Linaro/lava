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
Unit tests for dashboard_app.views.test_run_list
"""

import unittest
from django.http import HttpResponseForbidden, HttpResponse
from django.contrib.auth.models import User, Group
from django.core.urlresolvers import reverse
from django_testscenarios.ubertest import TestCaseWithScenarios

from dashboard_app.tests import fixtures
from dashboard_app.tests.utils import TestClient

# pylint: disable=too-many-ancestors,no-member


class TestRunListViewAnonymousTest(TestCaseWithScenarios):

    scenarios = [
        ('anonymous_stream', {
            'pathname': '/anonymous/',
        }),
        ('anonymous_named_stream', {
            'pathname': '/anonymous/name/',
        }),
        ('public_personal_stream', {
            'pathname': '/public/personal/user/',
        }),
        ('public_personal_named_stream', {
            'pathname': '/public/personal/user/name/',
        }),
        ('public_team_stream', {
            'pathname': '/public/team/group/',
        }),
        ('public_team_named_stream', {
            'pathname': '/public/team/group/name/',
        }),
        ('private_personal_stream', {
            'pathname': '/private/personal/user/',
        }),
        ('private_personal_named_stream', {
            'pathname': '/private/personal/user/name/',
        }),
        ('private_team_stream', {
            'pathname': '/private/team/group/',
        }),
        ('private_team_named_stream', {
            'pathname': '/private/team/group/name/',
        }),
    ]

    def setUp(self):
        super(TestRunListViewAnonymousTest, self).setUp()
        self.bundle_stream = fixtures.create_bundle_stream(self.pathname)
        self.user = None
        self.url = reverse("lava_dashboard_test_run_list", args=[self.bundle_stream.pathname])

    def test_status_code(self):
        response = self.client.get(self.url)
        if self.bundle_stream.is_accessible_by(self.user):
            self.assertEqual(response.status_code, 200)
        else:
            self.assertIsInstance(response, HttpResponseForbidden)

    def test_template_used(self):
        response = self.client.get(self.url)
        if self.bundle_stream.is_accessible_by(self.user):
            self.assertTemplateUsed(response,
                                    "dashboard_app/test_run_list.html")
        else:
            self.assertIsInstance(response, HttpResponseForbidden)


class TestRunListViewAuthorizedTest(TestRunListViewAnonymousTest):

    def setUp(self):
        super(TestRunListViewAuthorizedTest, self).setUp()
        self.client = TestClient()
        self.user = User.objects.get_or_create(username="user")[0]
        self.group = Group.objects.get_or_create(name="group")[0]
        self.user.groups.add(self.group)
        self.client.login_user(self.user)
