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
Unit tests for dashboard_app.views.bundle_stream_list
"""

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse

from dashboard_app.tests import fixtures
from dashboard_app.tests.utils import (
    DashboardViewsTestCase,
    TestClient,
)


class BundleStreamListViewAnonymousTest(DashboardViewsTestCase):

    scenarios = [
        ('empty', {
            'bundle_streams': [],
        }),
        ('public_streams', {
            'bundle_streams': [
                '/anonymous/',
                '/anonymous/name/',
                '/public/personal/user/',
                '/public/personal/user/name/',
                '/public/team/group/',
                '/public/team/group/name/',
            ]
        }),
        ('private_streams', {
            'bundle_streams': [
                '/private/personal/user/',
                '/private/personal/user/name/',
                '/private/team/group/',
                '/private/team/group/name/',
            ]
        }),
    ]

    def setUp(self):
        super(BundleStreamListViewAnonymousTest, self).setUp()
        self.url = reverse("dashboard_app.views.bundle_stream_list")
        self.user = None

    def test_status_code(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_template_used(self):
        response = self.client.get(self.url)
        self.assertTemplateUsed(response,
                "dashboard_app/bundle_stream_list.html")

    def test_listed_bundles_are_the_ones_we_should_see(self):
        with fixtures.created_bundle_streams(self.bundle_streams) as bundle_streams:
            response = self.client.get(self.url)
            expected_bsl = sorted(
                    [bundle_stream.pk for bundle_stream in
                        bundle_streams if
                        bundle_stream.is_accessible_by(self.user)])
            effective_bsl = sorted(
                    [bundle_stream.pk for bundle_stream in
                        response.context['bundle_stream_list']])
            self.assertEqual(effective_bsl, expected_bsl)


class BundleStreamListViewAuthorizedTest(BundleStreamListViewAnonymousTest):

    def setUp(self):
        super(BundleStreamListViewAuthorizedTest, self).setUp()
        self.client = TestClient()
        self.user = User.objects.create(username='user')
        self.user.groups.create(name='group')
        self.client.login_user(self.user)
