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
Unit tests for dashboard_app.views.bundle_stream_detail
"""

from django.contrib.auth.models import User, Group

from dashboard_app.tests import fixtures
from dashboard_app.tests.utils import (
    DashboardViewsTestCase,
    TestClient,
)


class BundleStreamDetailViewAnonymousTest(DashboardViewsTestCase):

    _USER = "user"
    _GROUP = "group"
    _SLUG = "slug"

    scenarios = [
        ('public_stream', {'slug': '', 'user': 'public'}),
        ('public_named_stream', {'slug': _SLUG, 'user': 'public'}),
        ('private_stream', {'slug': '', 'user': _USER}),
        ('private_named_stream', {'slug': _SLUG, 'user': _USER}),
        ('team_stream', {'slug': '', 'group': _GROUP}),
        ('team_named_stream', {'slug': _SLUG, 'group': _GROUP})
    ]

    def setUp(self):
        super(BundleStreamDetailViewAnonymousTest, self).setUp()
        self.bundle_stream = fixtures.make_bundle_stream(dict(
            slug=self.slug,
            user=getattr(self, 'user', ''),
            group=getattr(self, 'group', '')))
        self.user = None

    def test_status_code(self):
        response = self.client.get("/streams" + self.bundle_stream.pathname)
        if self.bundle_stream.is_accessible_by(self.user):
            self.assertEqual(response.status_code, 200)
        else:
            self.assertEqual(response.status_code, 403)

    def test_template_used(self):
        response = self.client.get("/streams" + self.bundle_stream.pathname)
        if self.bundle_stream.is_accessible_by(self.user):
            self.assertTemplateUsed(response,
                "dashboard_app/bundle_stream_detail.html")
        else:
            self.assertTemplateUsed(response,
                "403.html")


class BundleStreamDetailViewAuthorizedTest(BundleStreamDetailViewAnonymousTest):

    def setUp(self):
        super(BundleStreamDetailViewAuthorizedTest, self).setUp()
        self.client = TestClient()
        self.user = User.objects.get_or_create(username=self._USER)[0]
        self.group = Group.objects.get_or_create(name=self._GROUP)[0]
        self.user.groups.add(self.group)
        self.client.login_user(self.user)
