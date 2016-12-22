# Copyright (C) 2014 Linaro Limited
#
# Author: Tyler Baker <tyler.baker@linaro.org>
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

import pexpect

from collections import OrderedDict
from lava_dispatcher.pipeline.action import (
    Pipeline,
    InfrastructureError,
)
from lava_dispatcher.pipeline.actions.test import (
    TestAction,
)
from lava_dispatcher.pipeline.logical import (
    LavaTest,
    RetryAction,
)


class TestMonitor(LavaTest):
    """
    LavaTestMonitor Strategy object
    """
    def __init__(self, parent, parameters):
        super(TestMonitor, self).__init__(parent)
        self.action = TestMonitorAction()
        self.action.job = self.job
        self.action.section = self.action_type
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        # TODO: Add configurable timeouts
        required_parms = ['name', 'start',
                          'end', 'pattern']
        if 'monitors' in parameters:
            for monitor in parameters['monitors']:
                if all([x for x in required_parms
                        if x in monitor]):
                            return True
        else:
            return False

    @classmethod
    def needs_deployment_data(cls):
        return False

    @classmethod
    def needs_overlay(cls):
        return False

    @classmethod
    def has_shell(cls):
        return False


class TestMonitorRetry(RetryAction):

    def __init__(self):
        super(TestMonitorRetry, self).__init__()
        self.description = "Retry wrapper for lava-test-monitor"
        self.summary = "Retry support for Lava Test Monitoring"
        self.name = "lava-test-monitor-retry"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(TestMonitorAction())


class TestMonitorAction(TestAction):
    """
    Sets up and runs the LAVA Test Shell Definition scripts.
    Supports a pre-command-list of operations necessary on the
    booted image before the test shell can be started.
    """

    def __init__(self):
        super(TestMonitorAction, self).__init__()
        self.description = "Executing lava-test-monitor"
        self.summary = "Lava Test Monitor"
        self.name = "lava-test-monitor"
        self.test_suite_name = None
        self.report = {}
        self.fixupdict = {}
        self.patterns = {}

    def validate(self):
        super(TestMonitorAction, self).validate()

    def run(self, connection, args=None):
        # Sanity test: could be a missing deployment for some actions
        res = self.get_namespace_data(action='boot', label='shared', key='boot-result')
        if res != 'success':
            raise RuntimeError("No boot action result found")
        connection = super(TestMonitorAction, self).run(connection, args)
        if res != "success":
            self.logger.debug("Skipping test monitoring - previous boot attempt was not successful.")
            self.results.update({self.name: "skipped"})
            # FIXME: with predictable UID, could set each test definition metadata to "skipped"
            return connection

        if not connection:
            raise InfrastructureError("Connection closed")
        for monitor in self.parameters['monitors']:
            self.test_suite_name = monitor['name']

            self.fixupdict = monitor.get('fixupdict')

            # pattern order is important because we want to match the end before
            # it can possibly get confused with a test result
            self.patterns = OrderedDict()
            self.patterns["eof"] = pexpect.EOF
            self.patterns["timeout"] = pexpect.TIMEOUT
            self.patterns["end"] = monitor['end']
            self.patterns["test_result"] = monitor['pattern']

            # Find the start string before parsing any output.
            connection.prompt_str = monitor['start']
            connection.wait()
            self.logger.info("ok: start string found, lava test monitoring started")

            with connection.test_connection() as test_connection:
                while self._keep_running(test_connection, timeout=test_connection.timeout):
                    pass

        return connection

    def _keep_running(self, test_connection, timeout=120):
        self.logger.debug("test monitoring timeout: %d seconds" % timeout)
        retval = test_connection.expect(list(self.patterns.values()), timeout=timeout)
        return self.check_patterns(list(self.patterns.keys())[retval], test_connection)

    def check_patterns(self, event, test_connection):
        """
        Defines the base set of pattern responses.
        Stores the results of testcases inside the TestAction
        Call from subclasses before checking subclass-specific events.
        """
        ret_val = False
        results = {}
        if event == "end":
            self.logger.info("ok: end string found, lava test monitoring stopped")
            self.results.update({'status': 'passed'})
        elif event == "timeout":
            self.logger.warning("err: lava test monitoring has timed out")
            self.errors = "lava test monitoring has timed out"
            self.results.update({'status': 'failed'})
        elif event == "test_result":
            self.logger.info("ok: test case found")
            match = test_connection.match.groupdict()
            if 'result' in match:
                if self.fixupdict:
                    if match['result'] in self.fixupdict:
                        match['result'] = self.fixupdict[match['result']]
                if match['result'] not in ('pass', 'fail', 'skip', 'unknown'):
                    self.logger.error("error: bad test results: %s" % match['result'])
                else:
                    if 'test_case_id' in match:
                        results = {
                            'definition': self.test_suite_name.replace(' ', '-').lower(),
                            'case': match['test_case_id'].lower(),
                            'result': match['result']
                        }
                        if 'measurement' in match:
                            results.update({'measurement': match['measurement']})
                        if 'units' in match:
                            results.update({'units': match['units']})
                        self.logger.results(results)
            ret_val = True
        return ret_val
