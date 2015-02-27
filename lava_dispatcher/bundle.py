#!/usr/bin/python

# Copyright (C) 2014 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
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

import sys


class PrettyPrinter(object):

    def __init__(self, context):
        self.context = context

    def print_results(self, bundle):
        _print = self.context.log
        for test_run in bundle.get('test_runs', []):

            test_cases = test_run.get('test_results', [])
            if len(test_cases) > 0:

                test_id = test_run['test_id'].encode('utf-8')

                _print('')
                _print("=" * len(test_id))
                _print(test_id)
                _print("=" * len(test_id))
                _print('')

                has_measurements = \
                    any(map(lambda t: 'measurement' in t, test_cases))

                if has_measurements:
                    _print('%-40s %8s %20s' % ('Test case', 'Result',
                                               'Measurement'))
                    _print('%s %s %s' % ('-' * 40, '-' * 8, '-' * 20))
                else:
                    _print('%-40s %8s' % ('Test case', 'Result'))
                    _print('%s %s' % ('-' * 40, '-' * 8))

                for test_case in test_cases:
                    if 'test_case_id' not in test_case or \
                       'result' not in test_case:
                        continue

                    line = '%-40s %8s' % (test_case['test_case_id'],
                                          test_case['result'].upper())
                    if 'measurement' in test_case:
                        line += ' %s' % test_case['measurement']
                    if 'units' in test_case:
                        line += ' %s' % test_case['units']
                    self._print_with_color(line, test_case['result'].upper())

                _print('')

    def _print_with_color(self, line, result):
        if sys.stdout.isatty() and result in ['PASS', 'FAIL']:
            colors = {
                'PASS': 2,
                'FAIL': 1,
            }
            line = "\033[38;5;%sm" % colors[result] + line + "\033[m"
        self.context.log(line)
