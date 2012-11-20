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

import logging


class SignalHandler(object):

    def __init__(self, testdef):
        self.testdef = testdef

    def start(self):
        pass

    def

class SignalDirector(object):

    def __init__(self, client, handlers):
        self.client = client
        self.handlers = handlers
        self._test_run_data = []
        self._current_run_data = None
        self._current_case_data = None

    def signal(self, name, params):
        handler = getattr(self, '_on_' + name, None)
        if not handler:
            logging.warning("unrecognized signal: %s %s", name, params)
        else:
            handler(*params)

    def _on_STARTRUN(self, test_run_id):
        self._cur_handler = self.handlers
        self._test_run_data.append((test_id, self._current_run_data))

    def _on_ENDRUN(self, testrun_idx, test_id):
        self._current_run_data = None

    def _on_STARTTC(self, test_case_id):
        if self._current_run_data is None:
            raise RuntimeError("STARTTC outside test run?")
        self._current_case_data = {}
        self._current_run_data.append((test_case_id, self._current_case_data))
        self.start_test_case(self._current_case_data)

    def _on_ENDTC(self, test_case_id):
        if self._current_case_data is None:
            raise RuntimeError("ENDTC without start?")
        self.end_test_case(self._current_case_data)
        self._current_case_data = None

    def postprocess_bundle(self, bundle):
        print bundle
        print self._test_run_data
        for i, test_run in enumerate(bundle['test_runs']):
            test_id, run_data = self._test_run_data[i]
            if test_id != test_run['test_id']:
                XXX
            for j, result in enumerate(test_run['test_results']):
                test_case_id, case_data = run_data[j]
                if test_case_id != result['test_case_id']:
                    YYY
                self.postprocess_result(result, case_data)
                # Could check here that result still validates.

    def start_test_case(self, case_data):
        pass

    def end_test_case(self, case_data):
        pass

    def postprocess_result(self, result, case_data):
        pass


