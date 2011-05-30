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
from django_testscenarios.ubertest import TestCase


class XMLRPCViewsTests(TestCase):

    def test_request_context_was_used(self):
        url = reverse("dashboard_app.views.dashboard_xml_rpc_handler")
        response = self.client.get(url)
        # This is ugly because response.context is a list
        self.assertTrue(any((isinstance(context, RequestContext) for context in response.context)))
