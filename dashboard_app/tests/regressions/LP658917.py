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

from django_testscenarios.ubertest import TestCase

from dashboard_app.models import Bundle
from dashboard_app.xmlrpc import DashboardAPI
from pkg_resources import resource_string

from dashboard_app.tests import fixtures

class LP658917(TestCase):


    def setUp(self):
        super(LP658917, self).setUp()
        self.bundle_stream = fixtures.create_bundle_stream("/anonymous/")
        self.dashboard_api = DashboardAPI()
        self.content_sha1 = None

    def tearDown(self):
        if self.content_sha1:
            Bundle.objects.get(content_sha1=self.content_sha1).delete_files()
        super(LP658917, self).tearDown()

    def test_658917(self):
        """TestCase.units is not assigned a null value"""
        try:
            self.content_sha1 = self.dashboard_api.put(
                resource_string(__name__, 'LP658917.json'),
                'LP658917.json', self.bundle_stream.pathname)
        except IntegrityError:
            self.fail("LP658917 regression, IntegrityError raised")
