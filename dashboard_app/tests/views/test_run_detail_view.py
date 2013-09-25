# Copyright (C) 2010 Linaro Limited
#
# Author: Deepti B. Kalakeri<deepti.kalakeri@linaro.org>
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


from django_testscenarios.ubertest import (TestCase, TestCaseWithScenarios)
from dashboard_app.models import BundleStream, TestRun
from django.contrib.auth.models import (User, Group)

from dashboard_app.tests.utils import TestClient


class TestRunDetailView(TestCase):

    fixtures = ["test_run_detail.json"] 

    def setUp(self):
        super(TestRunDetailView, self).setUp()
        self.test_run_url = TestRun.objects.get(pk=1).get_absolute_url()

    def testrun_valid_page_view(self):
        response = self.client.get(self.test_run_url)
        self.assertEqual(response.status_code, 200)

    def test_template_used(self):
        response = self.client.get(self.test_run_url)
        self.assertTemplateUsed(response,
                "dashboard_app/test_run_detail.html")

    #def testrun_invalid_page_view(self):
    #    invalid_uuid = "0000000-0000-0000-0000-000000000000" 
    #    invalid_test_run_url = reverse("dashboard_app.views.test_run_detail",
    #                                   args=[invalid_uuid])
    #    response = self.client.get(invalid_test_run_url)
    #    self.assertEqual(response.status_code, 404)


class TestRunViewAuth(TestCaseWithScenarios):

    _USER = "private_owner"
    _GROUP = "private_group"
    _UNRELATED_USER = "unrelated-user"
    fixtures = ["test_run_detail.json"] 

    scenarios = [
        ("anonymous_accessing_private", {
            "accessing_user": None,
            "resource_owner": _USER
        }),
        ("anonymous_accessing_shared", {
            "accessing_user": None, 
            "resource_owner": _GROUP
        }),
        ("unrelated_accessing_private", {
            "accessing_user": _UNRELATED_USER,
            "resource_owner": _USER,
        }),
        ("unrelated_accessing_shared", {
            "accessing_user": _UNRELATED_USER,
            "resource_owner": _GROUP
        }),
    ]

    def setUp(self):
        super(TestRunViewAuth, self).setUp()
        self.test_run_url = TestRun.objects.get(pk=1).get_absolute_url()

        # Set resource ownership to group or user
        bundle_stream = BundleStream.objects.get(pk=1)
        if self.resource_owner == self._GROUP:
            bundle_stream.group = Group.objects.create(name=self._USER)
        elif self.resource_owner == self._USER:
            bundle_stream.user = User.objects.create(username=self._USER)
        bundle_stream.is_public = False
        bundle_stream.is_anonymous = False
        bundle_stream.save()

        if self.accessing_user:
            self.accessing_user = User.objects.get_or_create(username=self.accessing_user)[0]
            self.client = TestClient()
            self.client.login_user(self.accessing_user)
       
    def test_run_unauth_access(self):
        response = self.client.get(self.test_run_url)
        self.assertEqual(response.status_code, 404)
