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
Tests for the Test model
"""

from django.db import IntegrityError
from django.test import TestCase
from django_testscenarios.ubertest import TestCaseWithScenarios

from dashboard_app.models import Test


class TestConstructionTests(TestCaseWithScenarios):

    scenarios = [
        ('simple1', {
            'test_id': 'org.linaro.testheads.android',
            'name': "Android test suite"}),
        ('simple2', {
            'test_id': 'org.mozilla.unit-tests',
            'name': "Mozilla unit test collection"})
    ]

    def test_construction(self):
        test = Test(test_id = self.test_id, name = self.name)
        test.save()
        self.assertEqual(test.test_id, self.test_id)
        self.assertEqual(test.name, self.name)

    def test_test_id_uniqueness(self):
        test = Test(test_id = self.test_id, name = self.name)
        test.save()
        test2 = Test(test_id = self.test_id)
        self.assertRaises(IntegrityError, test2.save)


class TestUnicodeTests(TestCase):

    def test_unicode_for_test_with_id(self):
        """Test.test_id used when Test.name is not set"""
        obj = Test(test_id="org.some_test")
        self.assertEqual(unicode(obj), "org.some_test")

    def test_unicode_for_test_with_name(self):
        """Test.name used when available"""
        obj = Test(name="Some Test")
        self.assertEqual(unicode(obj), "Some Test")

    def test_unicode_for_test_with_id_and_name(self):
        """Test.name takes precedence over Test.test_id"""
        obj = Test(name="Some Test", test_id="org.some_test")
        self.assertEqual(unicode(obj), "Some Test")
