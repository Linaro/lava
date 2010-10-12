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
Regression test for LP:658917
"""

from django.db import IntegrityError

from dashboard_app.tests.utils import RegressionTestCase


class LP658917(RegressionTestCase):

    def test_658917(self):
        """TestCase.units is not assigned a null value"""
        try:
            self.dashboard_api.put(
                self.get_test_data('LP658917.json'), 'LP658917.json',
                self.bundle_stream.pathname)
        except IntegrityError:
            self.fail("LP658917 regression, IntegrityError raised")
