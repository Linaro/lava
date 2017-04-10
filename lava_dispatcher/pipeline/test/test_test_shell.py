# Copyright (C) 2017 Linaro Limited
#
# Author: Neil Williams neil.williams@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import re
import os
import yaml
import decimal
from lava_dispatcher.pipeline.action import TestError, JobError
from lava_dispatcher.pipeline.test.test_basic import StdoutTestCase, Factory
from lava_dispatcher.pipeline.test.test_multi import DummyLogger


class FakeConnection(object):  # pylint: disable=too-few-public-methods

    def __init__(self, match):
        self.match = match


class TestPatterns(StdoutTestCase):

    def setUp(self):
        super(TestPatterns, self).setUp()
        self.testdef = os.path.join(os.path.dirname(__file__), 'testdefs', 'params.yaml')
        self.res_data = os.path.join(os.path.dirname(__file__), 'testdefs', 'result-data.txt')
        factory = Factory()
        self.job = factory.create_kvm_job("sample_jobs/kvm.yaml")
        self.job.logger = DummyLogger()
        self.job.validate()
        self.ret = False
        test_retry = [action for action in self.job.pipeline.actions if action.name == 'lava-test-retry'][0]
        self.test_shell = [action for action in test_retry.internal_pipeline.actions if action.name == 'lava-test-shell'][0]
        self.test_shell.logger = DummyLogger()

    def test_case_result(self):
        self.assertEqual([], self.job.pipeline.errors)
        self.assertTrue(os.path.exists(self.testdef))
        with open(self.testdef, 'r') as par:
            params = yaml.load(par)
        self.assertIn('parse', params.keys())

        line = 'test1a: pass'
        self.assertEqual(
            r'(?P<test_case_id>.*-*):\s+(?P<result>(pass|fail))',
            params['parse']['pattern'])
        match = re.search(params['parse']['pattern'], line)
        conn = FakeConnection(match)
        self.ret = self.test_shell.pattern_test_case_result(conn)
        self.assertTrue(self.ret)
        del conn

    def test_case_measurement(self):
        line = 'test1a: 5 pass'
        pattern = r'(?P<test_case_id>.*-*):\s+(?P<measurement>\d+)\s+(?P<result>(pass|fail))'
        comparison = {'measurement': '5', 'result': 'pass', 'test_case_id': 'test1a'}
        match = re.search(pattern, line)
        conn = FakeConnection(match)
        result = match.groupdict()
        self.assertEqual(comparison, result)
        self.assertEqual(result['measurement'], '5')
        self.ret = self.test_shell.pattern_test_case_result(conn)
        self.assertTrue(self.ret)
        del conn

    def test_invalid_measurement(self):
        line = 'test1a: Z pass'
        pattern = r'(?P<test_case_id>.*-*):\s+(?P<measurement>\w+)\s+(?P<result>(pass|fail))'
        comparison = {'measurement': 'Z', 'result': 'pass', 'test_case_id': 'test1a'}
        match = re.search(pattern, line)
        conn = FakeConnection(match)
        result = match.groupdict()
        self.assertEqual(comparison, result)
        self.assertEqual(result['measurement'], 'Z')
        with self.assertRaises(TestError):
            self.ret = self.test_shell.pattern_test_case_result(conn)
        with self.assertRaises(decimal.InvalidOperation):
            decimal.Decimal('Z')
        self.assertFalse(self.ret)
        del conn

    def test_signal_lxc_add(self):
        """
        test that a plain job without a protocol returns False.
        """
        self.assertFalse(self.test_shell.signal_lxc_add())

    def test_set_with_no_name(self):
        params = ['START']
        with self.assertRaises(JobError):
            self.test_shell.signal_test_set(params)
        params = ['START', 'set1']
        self.assertEqual('testset_start', self.test_shell.signal_test_set(params))
        params = ['STOP']
        self.assertEqual('testset_stop', self.test_shell.signal_test_set(params))

    def test_reference(self):
        params = ['case', 'pass']
        with self.assertRaises(TestError):
            self.test_shell.signal_test_reference(params)
