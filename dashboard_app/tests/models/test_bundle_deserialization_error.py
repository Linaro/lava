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
Tests for the BundleDeserializationError model
"""

from django.test import TestCase

from dashboard_app.models import BundleDeserializationError


class BundleDeserializationErrorTests(TestCase):

    def test_unicode(self):
        obj = BundleDeserializationError(error_message="boom")
        self.assertEqual(unicode(obj), u"boom")
