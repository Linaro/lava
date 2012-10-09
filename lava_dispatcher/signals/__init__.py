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
import logging
import imp
import os


class BaseSignalHandler(object):
    """
    Base class for adding signal callbacks to the dispatcher for the
    lava-test-shell
    """

    def __init__(self, client):
        self.client = client

    def on_signal(self, name, params):
        raise NotImplementedError(self.on_signal)

    def postprocess_bundle(self, bundle):
        raise NotImplementedError(self.postprocess_bundle)


class PerTestCaseSignalHandler(BaseSignalHandler):

    def __init__(self, client):
        super(PerTestCaseSignalHandler, self).__init__(client)
        self._test_run_data = []
        self._current_run_data = None

    def on_signal(self, name, params):
        handler = getattr(self, '_on_signal_' + name, None)
        if not handler:
            logging.warning("unrecognized signal: %s %s", name, params)
        else:
            handler(*params)

    def _on_STARTRUN(self, testrun_idx, test_id):
        self._current_run_data = []
        self._test_run_data.append((test_id, self._current_run_data))

    def _on_ENDRUN(self, testrun_idx, test_id):
        self._current_run_data = None

    def _on_STARTTC(self, test_case_id):
        if not self._current_run_data:
            raise RuntimeError("STARTTC outside test run?")
        self._current_case_data = {}
        self._current_run_data.append((test_case_id, self._current_case_data))
        self.start_test_case(self._current_case_data)

    def _on_ENDTC(self, test_case_id):
        if not self._current_case_data:
            raise RuntimeError("ENDTC without start?")
        self.end_test_case(self._current_case_data)
        self._current_case_data = None

    def postprocess_bundle(self, bundle):
        for i, test_run in enumerate(bundle['test_runs']):
            test_id, run_data = self._test_run_data[i]
            if test_id != test_run['test_id']:
                XXX
            for j, result in enumerate(test_run['results']):
                test_case_id, case_data = run_data[j]
                if test_case_id != result['test_case_id']:
                    YYY
                self.postprocess_result(result, case_data)

    def start_test_case(self, case_data):
        pass

    def end_test_case(self, case_data):
        pass

    def postprocess_result(self, result, case_data):
        pass


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
            signals[name] = cls
    return signals


def get_signals():
    signals = {}
    path = os.path.dirname(os.path.realpath(__file__))
    for f in glob.glob(os.path.join(path, "*.py")):
        module = imp.load_source("module", os.path.join(path, f))
        signals.update(_find_signals(module))
    return signals
