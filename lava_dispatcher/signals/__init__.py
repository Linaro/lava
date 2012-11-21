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

    def __init__(self, testdef_obj):
        self.testdef_obj = testdef_obj

    def start(self):
        pass

    def end(self):
        pass

    def starttc(self, test_case_id):
        pass

    def endtc(self, test_case_id):
        pass

    def custom_signal(self, signame, params):
        pass

    def postprocess_test_run(self, test_run):
        pass


class SignalDirector(object):

    def __init__(self, client, testdefs_by_uuid):
        self.client = client
        self.testdefs_by_uuid = testdefs_by_uuid
        self._test_run_data = []
        self._cur_handler = None

    def signal(self, name, params):
        handler = getattr(self, '_on_' + name, None)
        if not handler:
            if self._cur_handler:
                self._cur_handler.custom_signal(name, params)
        else:
            handler(*params)

    def _on_STARTRUN(self, test_run_id, uuid):
        self._cur_handler = None
        testdef_obj = self.testdefs_by_uuid.get(test_run_id)
        if testdef_obj:
            self._cur_handler = testdef_obj.handler
        if self._cur_handler:
            self._cur_handler.start()

    def _on_ENDRUN(self, test_run_id, uuid):
        if self._cur_handler:
            self._cur_handler.end()

    def _on_STARTTC(self, test_case_id):
        if self._cur_handler:
            self._cur_handler.starttc(test_case_id)

    def _on_ENDTC(self, test_case_id):
        if self._cur_handler:
            self._cur_handler.endtc(test_case_id)

    def postprocess_bundle(self, bundle):
        for test_run in bundle['test_runs']:
            uuid = test_run['analyzer_assigned_uuid']
            testdef_obj = self.testdefs_by_uuid.get(uuid)
            if testdef_obj.handler:
                testdef_obj.handler.postprocess_test_run(test_run)

