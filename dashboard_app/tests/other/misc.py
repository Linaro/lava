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
Miscellaneous unit tests
"""

from django_testscenarios import TestCaseWithScenarios

from dashboard_app.models import BundleStream


class DjangoTestCaseWithScenarios(TestCaseWithScenarios):

    scenarios = [
            ('a', {}),
            ('b', {}),
            ]

    def test_database_is_empty_at_start_of_test(self):
        self.assertEqual(BundleStream.objects.all().count(), 0)
        stream = BundleStream.objects.create(slug='')
