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
Tests for the TestResult model
"""
import datetime

from django_testscenarios.ubertest import TestCase, TestCaseWithScenarios

from dashboard_app.models import TestRun, TestResult


class TestResultDurationTests(TestCaseWithScenarios):

    scenarios = [
        ('none_is_null', {
            'duration': None,
            'microseconds': None,
        }),
        ('0_is_0', {
            'duration': datetime.timedelta(days=0, seconds=0, microseconds=0),
            'microseconds': 0,
        }),
        ('microseconds_are_just_microseconds', {
            'duration': datetime.timedelta(microseconds=1),
            'microseconds': 1,
        }),
        ('second_is_10e6_microseconds', {
            'duration': datetime.timedelta(seconds=1),
            'microseconds': 10**6,
        }),
        ('day_is_24_times_60_times_60_times_10e6_microseconds', {
            'duration': datetime.timedelta(days=1),
            'microseconds': 24 * 60 * 60 * 10 ** 6,
        }),
        ('microseconds_seconds_and_days_are_used', {
            'duration': datetime.timedelta(days=1, seconds=1, microseconds=1),
            'microseconds': (
                24 * 60 * 60 * (10 ** 6) +
                10 ** 6 +
                1)
        }),
    ]

    def test_duration_to_microseconds(self):
        obj = TestResult()
        obj.duration = self.duration
        self.assertEqual(self.microseconds, obj.microseconds)

    def test_microseconds_to_duration(self):
        obj = TestResult()
        obj.microseconds = self.microseconds
        self.assertEqual(self.duration, obj.duration)


class TestResultUnicodeTests(TestCase):

    def test_test_result__pass(self):
        test_run = TestRun(analyzer_assigned_uuid="00000000-0000-0000-0000-000000000004")
        test_result = TestResult(test_run=test_run, relative_index=1)
        self.assertIn("00000000-0000-0000-0000-000000000004/1", unicode(test_result))
