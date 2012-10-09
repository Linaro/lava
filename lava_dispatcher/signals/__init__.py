#!/usr/bin/python

# Copyright (C) 2012 Linaro Limited
#
# Author: Andy Doan <andy.doan@linaro.org>
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

import glob
import imp
import os
import time


class BaseSignal(object):
    """
    Base class for adding signal callbacks to the dispatcher for the
    lava-test-shell
    """

    DURATION = 'duration'

    def __init__(self):
        self._data = {}

    def on_test_run_start(self, action, testrun_idx, test_id):
        d = self.get_test_run_data(testrun_idx, test_id)
        d[self.DURATION] = time.time()
        return d

    def on_test_run_end(self, action, testrun_idx, test_id):
        d = self.get_test_run_data(testrun_idx, test_id)
        start = d[self.DURATION]
        d[self.DURATION] = time.time() - start
        return d

    def on_test_case_start(self, action, run_idx, test_id, test_case):
        d = self.get_test_case_data(run_idx, test_id, test_case)
        d[self.DURATION] = time.time()
        return d

    def on_test_case_end(self, action, run_idx, test_id, test_case):
        d = self.get_test_case_data(run_idx, test_id, test_case)
        start = d[self.DURATION]
        d[self.DURATION] = time.time() - start
        return d

    def get_test_run_data(self, testrun_idx, test_id):
        """
        Returns a dictionary to store test run information in.
        """
        key = '%d_%s' % (testrun_idx, test_id)
        if key not in self._data:
            self._data[key] = {}
        return self._data[key]

    def get_test_case_data(self, testrun_idx, test_id, test_case):
        """
        Based on get_test_run_data, it inserts a key named
        "testcase_<test_case>" into the test run data with a dictionary value
        where test case data can be stored
        """
        data = self.get_test_run_data(testrun_idx, test_id)
        key = 'testcase_%s' % test_case
        if key not in data:
            data[key] = {}
        return data


def _find_signals(module):
    signals = {}
    for name, cls in module.__dict__.iteritems():
        if name.startswith('signal_'):
            # the class can either explicitly specify a "signal_name" or,
            # we'll default it to the uppercase version of the classname
            # minus the signal_ prefix
            name = getattr(cls, 'signal_name', None)
            if not name:
                name = cls.__name__[7:].upper()
            signals[name] = cls()
    return signals


def get_signals():
    signals = {}
    path = os.path.dirname(os.path.realpath(__file__))
    for f in glob.glob(os.path.join(path, "*.py")):
        module = imp.load_source("module", os.path.join(path, f))
        signals.update(_find_signals(module))
    return signals

    def on_signal(self, action, cmd_runner, params):
        params = params.strip().split(' ', 1)

        label = None
        if len(params) == 2:
            label = params[1]

        if params[0] == 'start':
            data = self.on_start(label)
            self._put_data(action, label, time.time(), data)
        elif params[0] == 'stop':
            (start, data) = self._get_data(action, label)
            duration = time.time() - start
            self.on_stop(action, label, duration, data)
        else:
            raise RuntimeError(
                'Invalid action(%s), must be start/stop' % params)
