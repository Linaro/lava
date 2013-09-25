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
Tests for the TestRun model
"""

import datetime

from django_testscenarios.ubertest import TestCase

from dashboard_app.tests import fixtures
from dashboard_app.models import Test, TestRun


class TestRunTests(TestCase):

    _TEST_ID = "test_id"
    _BUNDLE_PATHNAME = "/anonymous/"
    _BUNDLE_CONTENT_FILENAME = "bundle.txt"
    _BUNDLE_CONTENT = "content not relevant"

    def test_construction(self):
        test = Test.objects.create(test_id=self._TEST_ID)
        analyzer_assigned_uuid = '9695b58e-bfe9-11df-a9a4-002163936223'
        analyzer_assigned_date = datetime.datetime(2010, 9, 14, 12, 20, 00)
        time_check_performed = False
        spec = [(self._BUNDLE_PATHNAME, self._BUNDLE_CONTENT_FILENAME,
                self._BUNDLE_CONTENT)]
        with fixtures.created_bundles(spec) as bundles:
            test_run = TestRun(
                bundle = bundles[0],
                test = test,
                time_check_performed=time_check_performed,
                analyzer_assigned_uuid = analyzer_assigned_uuid,
                analyzer_assigned_date = analyzer_assigned_date,
            )
            test_run.save()
            self.assertEqual(test_run.bundle, bundles[0])
            self.assertEqual(test_run.time_check_performed, time_check_performed)
            self.assertEqual(test_run.test, test)
            self.assertEqual(test_run.analyzer_assigned_uuid,
                             analyzer_assigned_uuid)

    def test_unicode(self):
        obj = TestRun(analyzer_assigned_uuid="0" * 16)
        self.assertIn(obj.analyzer_assigned_uuid, unicode(obj))
