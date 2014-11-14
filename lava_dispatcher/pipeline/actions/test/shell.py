# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
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
import logging
from collections import OrderedDict
from contextlib import contextmanager
from lava_dispatcher.pipeline.actions.test import handle_testcase, TestAction
from lava_dispatcher.pipeline.action import (
    Pipeline,
    RetryAction,
    JobError,
    LavaTest
)
from lava_dispatcher.pipeline.connection import BaseSignalHandler, SignalMatch


class TestShell(LavaTest):
    """
    LavaTestShell Strategy object
    """
    def __init__(self, parent, parameters):
        super(TestShell, self).__init__(parent)
        self.action = TestShellRetry()
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @contextmanager
    def test(self):
        pass

    @classmethod
    def accepts(cls, device, parameters):  # pylint: disable=unused-argument
        return True


class TestShellRetry(RetryAction):

    def __init__(self):
        super(TestShellRetry, self).__init__()
        self.description = "Retry wrapper for lava-test-shell"
        self.summary = "Retry support for Lava Test Shell"
        self.name = "lava-test-retry"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(TestShellAction())

    def cleanup(self):
        pass


class TestShellAction(TestAction):

    def __init__(self):
        super(TestShellAction, self).__init__()
        self.description = "Executing lava-test-runner"
        self.summary = "Lava Test Shell"
        self.name = "lava-test-shell"
        self.signal_director = self.SignalDirector()
        self.patterns = {}
        self.match = SignalMatch()

    def validate(self):
        if 'definitions' in self.parameters:
            for testdef in self.parameters['definitions']:
                if 'repository' not in testdef:
                    self.errors = "Repository missing from test definition"
        # Extend the list of patterns when creating subclasses.
        self.patterns.update({
            'exit': '<LAVA_TEST_RUNNER>: exiting',
            'eof': pexpect.EOF,
            'timeout': pexpect.TIMEOUT,
            'signal': r'<LAVA_SIGNAL_(\S+) ([^>]+)>',
        })
        super(TestShellAction, self).validate()

    def run(self, connection, args=None):
        """
        Common run function for subclasses which define custom patterns
        """
        if not connection:
            self.logger.debug("No connection!")

        if 'boot-result' not in self.data:
            self.logger.debug("No boot action result found")  # FIXME: this could be a missing deployment for some actions
        elif self.data['boot-result'] != 'success':
            self.logger.debug("Skipping test definitions - previous boot attempt was not successful.")
            self.results.update({self.name: 'skipped'})
            # FIXME: with predictable UID, could set each test definition metadata to "skipped"
            return connection
        self.logger.debug("Executing test definitions using %s" % connection.name)

        self.match = SignalMatch()

        # FIXME: a predictable UID could be calculated from existing data here.
        # instead, uuid is read from the params to set _current_handler
        # FIXME: can only be run once per TestAction, so collate all patterns for all test definitions.
        # (or work out the uuid from the signal params?)

        # FIXME: not being set
        if self.signal_director.test_uuid:
            self.patterns.update({
                'test_case': self.data['test'][self.signal_director.test_uuid]['testdef_pattern']['pattern'],
            })

        with connection.test_connection() as test_connection:
            try:
                # the structure of lava-test-runner means that there is just one TestAction and it must run all definitions
                test_connection.sendline(
                    "%s/bin/lava-test-runner %s" % (
                        self.data['lava_test_results_dir'],
                        self.data['lava_test_results_dir']),
                )
            except KeyboardInterrupt:
                self.errors = "Cancelled"
                return connection

            if self.timeout:
                test_connection.timeout = self.timeout.duration

            while self._keep_running(test_connection, test_connection.timeout):
                pass

        return connection

    def check_patterns(self, event, test_connection):
        """
        Defines the base set of pattern responses.
        Stores the results of testcases inside the TestAction
        Call from subclasses before checking subclass-specific events.
        """
        yaml_log = logging.getLogger("YAML")
        if event == 'exit':
            yaml_log.debug('   ok: lava_test_shell seems to have completed')
            return False

        elif event == 'eof':
            yaml_log.debug('   err: lava_test_shell connection dropped')
            self.errors = 'lava_test_shell connection dropped'
            return False

        elif event == 'timeout':
            # if target.is_booted():
            #    target.reset_boot()
            yaml_log.debug('   err: lava_test_shell has timed out')
            self.errors = 'lava_test_shell has timed out'
            return False

        elif event == 'signal':
            name, params = test_connection.match.groups()
            # YAML formatting log message
            yaml_log.debug("   Received signal: <%s> %s", name, params)
            params = params.split()
            if name == 'STARTRUN':
                self.signal_director.test_uuid = params[1]
            #    self._handle_testrun(params)
            if name == 'TESTCASE':
                data = handle_testcase(params)
                res = self.match.match(data)  # FIXME: rename!
                yaml_log.debug('   result: %s', res)
                self.data['test'][self.signal_director.test_uuid].setdefault('results', OrderedDict())

                # prevent losing data in the update
                # FIXME: support parameters and retries
                if res['test_case_id'] in self.data['test'][self.signal_director.test_uuid]['results']:
                    raise JobError("Duplicate test_case_id in results: %s", res['test_case_id'])
                # turn the result dict inside out to get the unique test_case_id as key and result as value
                self.results.update({
                    res['test_case_id']: res['result']
                })
            try:
                self.signal_director.signal(name, params)
            except KeyboardInterrupt:
                raise KeyboardInterrupt
            # except:
            #     logging.exception("on_signal failed")
            # force output in case there was none but minimal content to increase speed.
            test_connection.sendline('#')
            return True

        elif event == 'test_case':
            match = test_connection.match
            if match is pexpect.TIMEOUT:
                # if target.is_booted():
                #    target.reset_boot()
                yaml_log.debug('   err: lava_test_shell has timed out (test_case)')
            else:
                res = self.match.match(match.groupdict())  # FIXME: rename!
                yaml_log.debug('   result: %s', res)
                self.data['test'][self.signal_director.test_uuid].setdefault('results', {})
                self.data['test'][self.signal_director.test_uuid]['results'].update({
                    {res['test_case_id']: res}
                })
                return True

        return False

    def cleanup(self):
        pass

    def _keep_running(self, test_connection, timeout):
        yaml_log = logging.getLogger("YAML")
        yaml_log.debug("   expect timeout: %d", timeout)
        retval = test_connection.expect(list(self.patterns.values()), timeout=timeout)
        return self.check_patterns(list(self.patterns.keys())[retval], test_connection)

    class SignalDirector(object):

        # FIXME: create proxy handlers
        def __init__(self):
            """
            Base SignalDirector for singlenode jobs.
            MultiNode and LMP jobs need to create a suitable derived class as both also require
            changes equivalent to the old _keep_running functionality.

            SignalDirector is the link between the Action and the Connection. The Action uses
            the SignalDirector to interact with the I/O over the Connection.
            """
            self._cur_handler = BaseSignalHandler(None)
            self.test_uuid = None

        def signal(self, name, params):
            yaml_log = logging.getLogger("YAML")
            handler = getattr(self, '_on_' + name.lower(), None)
            if not handler and self._cur_handler:
                handler = self._cur_handler.custom_signal
                params = [name] + list(params)
            if handler:
                try:
                    # The alternative here is to drop the getattr and have a long if:elif:elif:else.
                    # Without python support for switch, this gets harder to read than using
                    # a getattr lookup for the callable (codehelp). So disable checkers:
                    # noinspection PyCallingNonCallable
                    handler(*params)  # pylint: disable=star-args
                except KeyboardInterrupt:
                    raise KeyboardInterrupt
                except JobError:
                    yaml_log.debug("    err: handling signal %s failed", name)
                    return False
                return True

        def postprocess_bundle(self, bundle):
            pass

        # FIXME: remove unused arguments
        def _on_startrun(self, test_run_id, uuid):
            self._cur_handler = None
            # FIXME: adapt old code to work for more than a single test definition
#            testdef_obj = get_testdef_obj_with_uuid(self.testdef_objs, uuid)
#            if testdef_obj:
#                self._cur_handler = testdef_obj.handler
            if self._cur_handler:
                self._cur_handler.start()

        def _on_endrun(self, test_run_id, uuid):
            if self._cur_handler:
                self._cur_handler.end()

        def _on_starttc(self, test_case_id):
            if self._cur_handler:
                self._cur_handler.starttc(test_case_id)

        def _on_endtc(self, test_case_id):
            if self._cur_handler:
                self._cur_handler.endtc(test_case_id)
