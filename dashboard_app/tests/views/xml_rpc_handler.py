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
Unit tests for dashboard_app.views.dashboard_xml_rpc_handler
"""

from django.core.urlresolvers import reverse
from django.template import RequestContext

from dashboard_app.tests.utils import DashboardViewsTestCase


class XMLRPCViewsTests(DashboardViewsTestCase):

    def test_request_context_was_used(self):
        response = self.client.get(reverse("dashboard_app.dashboard_xml_rpc_handler"))
        self.assertTrue(isinstance(response.context, RequestContext))

