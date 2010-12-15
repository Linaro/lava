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
from django.test import TestCase
from django.core.urlresolvers import reverse
import random


class TestRunDetailView(TestCase):
    fixtures = ["test_run_detail.json", "analyzer_assigned_uuid"] 
    test_run_url = reverse("dashboard_app.views.test_run_detail", 
                           args=["19bbbb9a-02a0-11e0-b91e-0015587c0f4d"]) 

    def testrun_valid_page_view(self):
        response = self.client.get(self.test_run_url)
        self.assertEqual(response.status_code, 200)

    def test_template_used(self):
        response = self.client.get(self.test_run_url)
        self.assertTemplateUsed(response,
                "dashboard_app/test_run_detail.html")

    def testrun_invalid_page_view(self):
        random_val = str(random.randint(1, 9))
        invalid_uuid = "1%sbbbb9a-02a0-11e0-b91e-0015587c0f%sd" % (random_val, random_val)
        invalid_test_run_url = reverse("dashboard_app.views.test_run_detail",
                                       args=[invalid_uuid])
        response = self.client.get(invalid_test_run_url)
        self.assertEqual(response.status_code, 404)
