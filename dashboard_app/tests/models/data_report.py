# Copyright (C) 2010, 2011 Linaro Limited
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
Tests for data reports
"""

from django.core.urlresolvers import reverse
from django_testscenarios.ubertest import TestCase
from mocker import Mocker, expect

from dashboard_app.models import DataReport


class DataReportTests(TestCase):

    def test_template_context_has_API_URL(self):
        mocker = Mocker()
        report = mocker.patch(DataReport())
        expect(report._get_raw_html()).result("{{API_URL}}")
        with mocker:
            observed = report.get_html()
            expected = reverse("dashboard_app.views.dashboard_xml_rpc_handler")
            self.assertEqual(observed, expected)

    def test_template_context_does_not_have_RequestContext_things(self):
        mocker = Mocker()
        report = mocker.patch(DataReport())
        expect(report._get_raw_html()).result("{{MEDIA_URL}}")
        with mocker:
            observed = report.get_html()
            expected = ""
            self.assertEqual(observed, expected)

