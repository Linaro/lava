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
Tests for Cross-Site Request Forgery middleware configuration
"""
import xmlrpclib

import django
from django.core.urlresolvers import reverse

from dashboard_app.tests.utils import CSRFTestCase


class CSRFConfigurationTestCase(CSRFTestCase):

    def setUp(self):
        super(CSRFConfigurationTestCase, self).setUp()
        self.login_path = reverse("django.contrib.auth.views.login")

    def test_csrf_token_present_in_login_page(self):
        if django.VERSION[:2] == (1, 1):
            # This feature is not supported on django 1.1
            return
        response = self.client.get(self.login_path)
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_cross_site_login_fails(self):
        if django.VERSION[:2] == (1, 1):
            # This feature is not supported on django 1.1
            return
        response = self.client.post(self.login_path, {
            'user': 'user', 'pass': 'pass'})
        self.assertEquals(response.status_code, 403)

    def test_csrf_not_protecting_xml_rpc_views(self):
        """call version and check that we didn't get 403"""
        endpoint_path = reverse("xml-rpc")
        request_body = xmlrpclib.dumps((), methodname="version")
        response = self.client.post(endpoint_path, request_body, "text/xml")
        self.assertContains(response, "<methodResponse>", status_code=200)
