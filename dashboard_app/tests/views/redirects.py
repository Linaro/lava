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

from django.core.urlresolvers import reverse
from django_testscenarios.ubertest import TestCase

from dashboard_app.tests import fixtures


class RedirectTests(TestCase):

    _PATHNAME = "/anonymous/"
    _BUNDLE_TEXT = """
{
  "test_runs": [
    {
      "test_results": [
        {
          "test_case_id": "test-case-0", 
          "result": "pass"
        } 
      ], 
      "analyzer_assigned_date": "2010-10-15T22:04:46Z", 
      "time_check_performed": false, 
      "analyzer_assigned_uuid": "00000000-0000-0000-0000-000000000001",
      "test_id": "examples"
    }
  ], 
  "format": "Dashboard Bundle Format 1.0"
}
    """
    _BUNDLE_NAME = "whatever.json"

    def setUp(self):
        super(RedirectTests, self).setUp()
        self.bundle = fixtures.create_bundle(self._PATHNAME, self._BUNDLE_TEXT, self._BUNDLE_NAME)
        self.bundle.deserialize()
        self.assertTrue(self.bundle.is_deserialized)

    def test_bundle_permalink(self):
        response = self.client.get(
            reverse("dashboard_app.views.redirect_to_bundle",
                    args=(self.bundle.content_sha1, )))
        self.assertRedirects(response, self.bundle.get_absolute_url())

    def test_bundle_permalink_trailing(self):
        response = self.client.get(
            reverse("dashboard_app.views.redirect_to_bundle",
                    args=(self.bundle.content_sha1, 'trailing/')))
        self.assertRedirects(
            response, self.bundle.get_absolute_url() + 'trailing/',
            target_status_code=404)

    def test_bundle_permalink_query_string(self):
        response = self.client.get(
            reverse("dashboard_app.views.redirect_to_bundle",
                    args=(self.bundle.content_sha1, )), data={'foo': 'bar'})
        self.assertRedirects(
            response, self.bundle.get_absolute_url()+'?foo=bar')

    def test_test_run_permalink(self):
        test_run = self.bundle.test_runs.all()[0]
        response = self.client.get(
            reverse("dashboard_app.views.redirect_to_test_run",
                    args=(test_run.analyzer_assigned_uuid, )))
        self.assertRedirects(response, test_run.get_absolute_url())

    def test_test_run_permalink_trailing(self):
        test_run = self.bundle.test_runs.all()[0]
        response = self.client.get(
            reverse("dashboard_app.views.redirect_to_test_run",
                    args=(test_run.analyzer_assigned_uuid, 'trailing/')))
        self.assertRedirects(
            response, test_run.get_absolute_url() + 'trailing/',
            target_status_code=404)

    def test_test_run_permalink_query_string(self):
        test_run = self.bundle.test_runs.all()[0]
        response = self.client.get(
            reverse("dashboard_app.views.redirect_to_test_run",
                    args=(test_run.analyzer_assigned_uuid, )),
            data={'foo': 'bar'})
        self.assertRedirects(
            response, test_run.get_absolute_url() + '?foo=bar')

    def test_test_result_permalink(self):
        test_run = self.bundle.test_runs.all()[0]
        test_result = test_run.test_results.all()[0]
        response = self.client.get(
            reverse("dashboard_app.views.redirect_to_test_result",
                    args=(test_run.analyzer_assigned_uuid,
                          test_result.relative_index)))
        self.assertRedirects(response, test_result.get_absolute_url())

    def test_test_result_permalink_trailing(self):
        test_run = self.bundle.test_runs.all()[0]
        test_result = test_run.test_results.all()[0]
        response = self.client.get(
            reverse("dashboard_app.views.redirect_to_test_result",
                    args=(test_run.analyzer_assigned_uuid,
                          test_result.relative_index, 'trailing/')))
        self.assertRedirects(
            response, test_result.get_absolute_url() + 'trailing/',
            target_status_code=404)

    def test_test_result_permalink_query_string(self):
        test_run = self.bundle.test_runs.all()[0]
        test_result = test_run.test_results.all()[0]
        response = self.client.get(
            reverse("dashboard_app.views.redirect_to_test_result",
                    args=(test_run.analyzer_assigned_uuid,
                          test_result.relative_index)),
            data={'foo': 'bar'})
        self.assertRedirects(
            response, test_result.get_absolute_url() + '?foo=bar')
