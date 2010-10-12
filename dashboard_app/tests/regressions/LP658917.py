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


# --------------------------8< cut here >8 ---------------------------
# The rest should be moved to helper tests once that branch lands. For
# the time being it can stay here not to cause additional conflicts in
# merging test split-up

from django.test import TestCase

from dashboard_app.models import Test
from dashboard_app.helpers import BundleDeserializer
from launch_control.thirdparty.mocker import MockerTestCase, expect

class BundleDeserializerTests(MockerTestCase, TestCase):

    _TEST_ID = "test_id"
    _TEST_CASE_ID = "test_case_id"
    _UNITS = "units"

    def test_mem2db_TestCase__no_test_case(self):
        c_test_result = self.mocker.mock()
        expect(c_test_result.test_case_id).result(None)
        s_test = self.mocker.mock()
        self.mocker.replay()
        deserializer = BundleDeserializer()
        s_test_case = deserializer._mem2db_TestCase(c_test_result, s_test)
        self.assertEqual(s_test_case, None)

    def test_mem2db_TestCase_test_case_with_units(self):
        """
        Make sure we use the units field in test result when it is
        provided and is not null
        """
        c_test_result = self.mocker.mock()
        c_test_result.test_case_id
        self.mocker.count(2)
        self.mocker.result(self._TEST_CASE_ID)
        expect(c_test_result.units).result(self._UNITS)
        s_test = Test.objects.create(test_id = self._TEST_ID)
        self.mocker.replay()
        deserializer = BundleDeserializer()
        s_test_case = deserializer._mem2db_TestCase(c_test_result, s_test)
        self.assertEqual(s_test_case.units, self._UNITS)
        self.assertEqual(s_test_case.test_case_id, self._TEST_CASE_ID)

    def test_mem2db_TestCase_test_case_without_units(self):
        """
        Make sure units default to '' when we create the test case and
        test result has no units defined.
        """
        c_test_result = self.mocker.mock()
        c_test_result.test_case_id
        self.mocker.count(2)
        self.mocker.result(self._TEST_CASE_ID)
        expect(c_test_result.units).result(None)
        s_test = Test.objects.create(test_id = self._TEST_ID)
        self.mocker.replay()
        deserializer = BundleDeserializer()
        s_test_case = deserializer._mem2db_TestCase(c_test_result, s_test)
        self.assertEqual(s_test_case.units, '')
        self.assertEqual(s_test_case.test_case_id, self._TEST_CASE_ID)
