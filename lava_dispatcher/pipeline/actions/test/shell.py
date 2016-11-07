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

import re
import sys
import time
import yaml
import logging
import pexpect
from collections import OrderedDict

from lava_dispatcher.pipeline.actions.test import (
    TestAction,
    handle_testcase
)
from lava_dispatcher.pipeline.action import (
    InfrastructureError,
    Pipeline,
    JobError,
    TestError
)
from lava_dispatcher.pipeline.logical import (
    LavaTest,
    RetryAction
)
from lava_dispatcher.pipeline.connection import (
    BaseSignalHandler,
    SignalMatch
)
from lava_dispatcher.pipeline.utils.constants import (
    DEFAULT_SHELL_PROMPT,
    DEFAULT_V1_PATTERN,
    DEFAULT_V1_FIXUP,
)
if sys.version > '3':
    from functools import reduce  # pylint: disable=redefined-builtin

# pylint: disable=too-many-branches,too-many-statements,too-many-instance-attributes,logging-not-lazy


class TestShell(LavaTest):
    """
    LavaTestShell Strategy object
    """
    def __init__(self, parent, parameters):
        super(TestShell, self).__init__(parent)
        self.action = TestShellRetry()
        self.action.job = self.job
        self.action.section = self.action_type
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):  # pylint: disable=unused-argument
        if ('definition' in parameters) or ('definitions' in parameters):
            return True
        else:
            return False


class TestShellRetry(RetryAction):

    def __init__(self):
        super(TestShellRetry, self).__init__()
        self.description = "Retry wrapper for lava-test-shell"
        self.summary = "Retry support for Lava Test Shell"
        self.name = "lava-test-retry"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(TestShellAction())


# FIXME: move to utils and call inside the overlay
class PatternFixup(object):

    def __init__(self, testdef, count):
        """
        Like all good arrays, the count is expected to start at zero.
        Avoid calling from validate() or populate() - this needs the
        RepoAction to be running.
        """
        super(PatternFixup, self).__init__()
        self.pat = DEFAULT_V1_PATTERN
        self.fixup = DEFAULT_V1_FIXUP
        if isinstance(testdef, dict) and 'metadata' in testdef:
            self.testdef = testdef
            self.name = "%d_%s" % (count, reduce(dict.get, ['metadata', 'name'], testdef))
        else:
            self.testdef = {}
            self.name = None

    def valid(self):
        return self.fixupdict() and self.pattern() and self.name

    def update(self, pattern, fixupdict):
        if not isinstance(pattern, str):
            raise TestError("Unrecognised test parse pattern type: %s" % type(pattern))
        try:
            self.pat = re.compile(pattern, re.M)
        except re.error as exc:
            raise TestError("Error parsing regular expression %r: %s" % (self.pat, exc.message))
        self.fixup = fixupdict

    def fixupdict(self):
        if 'parse' in self.testdef and 'fixupdict' in self.testdef['parse']:
            self.fixup = self.testdef['parse']['fixupdict']
        return self.fixup

    def pattern(self):
        if 'parse' in self.testdef and 'pattern' in self.testdef['parse']:
            self.pat = self.testdef['parse']['pattern']
            if not isinstance(self.pat, str):
                raise TestError("Unrecognised test parse pattern type: %s" % type(self.pat))
            try:
                self.pat = re.compile(self.pat, re.M)
            except re.error as exc:
                raise TestError("Error parsing regular expression %r: %s" % (self.pat, exc.message))
        return self.pat


class TestShellAction(TestAction):
    """
    Sets up and runs the LAVA Test Shell Definition scripts.
    Supports a pre-command-list of operations necessary on the
    booted image before the test shell can be started.
    """

    def __init__(self):
        super(TestShellAction, self).__init__()
        self.description = "Executing lava-test-runner"
        self.summary = "Lava Test Shell"
        self.name = "lava-test-shell"
        self.signal_director = self.SignalDirector(None)  # no default protocol
        self.patterns = {}
        self.signal_match = SignalMatch()
        self.definition = None
        self.testset_name = None  # FIXME
        self.report = {}
        self.start = None
        self.testdef_dict = {}
        # noinspection PyTypeChecker
        self.pattern = PatternFixup(testdef=None, count=0)

    def _reset_patterns(self):
        # Extend the list of patterns when creating subclasses.
        self.patterns = {
            "exit": "<LAVA_TEST_RUNNER>: exiting",
            "eof": pexpect.EOF,
            "timeout": pexpect.TIMEOUT,
            "signal": r"<LAVA_SIGNAL_(\S+) ([^>]+)>",
        }
        # noinspection PyTypeChecker
        self.pattern = PatternFixup(testdef=None, count=0)

    def validate(self):
        if "definitions" in self.parameters:
            for testdef in self.parameters["definitions"]:
                if "repository" not in testdef:
                    self.errors = "Repository missing from test definition"
        self._reset_patterns()
        super(TestShellAction, self).validate()

    def run(self, connection, args=None):
        """
        Common run function for subclasses which define custom patterns
        boot-result is a simple sanity test and only supports the most recent boot
        just to allow the test action to know if something has booted. Failed boots will timeout.
        A missing boot-result could be a missing deployment for some actions.
        """
        # Sanity test: could be a missing deployment for some actions
        if "boot-result" not in self.data:
            raise RuntimeError("No boot action result found")
        connection = super(TestShellAction, self).run(connection, args)
        if self.data["boot-result"] != "success":
            self.logger.debug("Skipping test definitions - previous boot attempt was not successful.")
            self.results.update({self.name: "skipped"})
            # FIXME: with predictable UID, could set each test definition metadata to "skipped"
            return connection

        if not connection:
            raise InfrastructureError("Connection closed")

        self.signal_director.connection = connection

        pattern_dict = {self.pattern.name: self.pattern}
        # pattern dictionary is the lookup from the STARTRUN to the parse pattern.
        self.set_common_data(self.name, 'pattern_dictionary', pattern_dict)

        self.logger.info("Executing test definitions using %s" % connection.name)
        if not connection.prompt_str:
            connection.prompt_str = [DEFAULT_SHELL_PROMPT]
            # FIXME: This should be logged whenever prompt_str is changed, by the connection object.
            self.logger.debug("Setting default test shell prompt %s", connection.prompt_str)
        connection.timeout = self.connection_timeout
        # force an initial prompt - not all shells will respond without an excuse.
        connection.sendline(connection.check_char)
        self.wait(connection)

        # use the string instead of self.name so that inheriting classes (like multinode)
        # still pick up the correct command.
        pre_command_list = self.get_common_data("lava-test-shell", 'pre-command-list')
        if pre_command_list and self.parameters['stage'] == 0:
            for command in pre_command_list:
                connection.sendline(command)

        with connection.test_connection() as test_connection:
            # the structure of lava-test-runner means that there is just one TestAction and it must run all definitions
            test_connection.sendline(
                "%s/bin/lava-test-runner %s/%s" % (
                    self.data["lava_test_results_dir"],
                    self.data["lava_test_results_dir"],
                    self.parameters['stage']),
                delay=self.character_delay)

            self.logger.info("Test shell will use the higher of the action timeout and connection timeout.")
            if self.timeout.duration > self.connection_timeout.duration:
                self.logger.info("Setting action timeout: %.0f seconds" % self.timeout.duration)
                test_connection.timeout = self.timeout.duration
            else:
                self.logger.info("Setting connection timeout: %.0f seconds" % self.connection_timeout.duration)
                test_connection.timeout = self.connection_timeout.duration

            while self._keep_running(test_connection, test_connection.timeout, connection.check_char):
                pass

        self.logger.debug(yaml.dump(self.report, default_flow_style=False))
        return connection

    def parse_v2_case_result(self, data, fixupdict=None):
        # FIXME: Ported from V1 - still needs integration
        if not fixupdict:
            fixupdict = {}
        res = {}
        for key in data:
            res[key] = data[key]

            if key == 'measurement':
                # Measurement accepts non-numeric values, but be careful with
                # special characters including space, which may distrupt the
                # parsing.
                res[key] = res[key]

            elif key == 'result':
                if res['result'] in fixupdict:
                    res['result'] = fixupdict[res['result']]
                if res['result'] not in ('pass', 'fail', 'skip', 'unknown'):
                    logging.error('Bad test result: %s', res['result'])
                    res['result'] = 'unknown'

        if 'test_case_id' not in res:
            self.logger.warning(
                """Test case results without test_case_id (probably a sign of an """
                """incorrect parsing pattern being used): %s""", res)

        if 'result' not in res:
            self.logger.warning(
                """Test case results without result (probably a sign of an """
                """incorrect parsing pattern being used): %s""", res)
            self.logger.warning('Setting result to "unknown"')
            res['result'] = 'unknown'

        return res

    def check_patterns(self, event, test_connection, check_char):  # pylint: disable=too-many-locals
        """
        Defines the base set of pattern responses.
        Stores the results of testcases inside the TestAction
        Call from subclasses before checking subclass-specific events.
        """
        ret_val = False
        if event == "exit":
            self.logger.info("ok: lava_test_shell seems to have completed")
            self.testset_name = None

        elif event == "eof":
            self.logger.warning("err: lava_test_shell connection dropped")
            self.errors = "lava_test_shell connection dropped"
            self.testset_name = None

        elif event == "timeout":
            self.logger.warning("err: lava_test_shell has timed out")
            self.errors = "lava_test_shell has timed out"
            self.testset_name = None

        elif event == "signal":
            name, params = test_connection.match.groups()
            self.logger.debug("Received signal: <%s> %s" % (name, params))
            params = params.split()
            if name == "STARTRUN":
                self.signal_director.test_uuid = params[1]
                self.definition = params[0]
                uuid = params[1]
                self.start = time.time()
                self.logger.info("Starting test lava.%s (%s)", self.definition, uuid)
                # set the pattern for this run from pattern_dict
                namespace = self.parameters.get('namespace', None)
                if namespace:
                    testdef_index = self.get_common_data(namespace, 'testdef_index')
                else:
                    testdef_index = self.get_common_data('test-definition', 'testdef_index')
                uuid_list = self.get_common_data('repo-action', 'uuid-list')
                for (key, value) in enumerate(testdef_index):
                    if self.definition == "%s_%s" % (key, value):
                        pattern = self.job.context['test'][uuid_list[key]]['testdef_pattern']['pattern']
                        fixup = self.job.context['test'][uuid_list[key]]['testdef_pattern']['fixupdict']
                        self.patterns.update({'test_case_result': re.compile(pattern, re.M)})
                        self.pattern.update(pattern, fixup)
                        self.logger.info("Enabling test definition pattern %r" % pattern)
                self.logger.results({
                    "definition": "lava",
                    "case": self.definition,
                    "uuid": uuid,
                    # The test is marked as failed and updated to "pass" when finished.
                    # If something goes wrong then it will stay to "fail".
                    "result": "fail"
                })
            elif name == "ENDRUN":
                self.definition = params[0]
                uuid = params[1]
                # remove the pattern for this run from pattern_dict
                self._reset_patterns()
                # catch error in ENDRUN being handled without STARTRUN
                if not self.start:
                    self.start = time.time()
                self.logger.info("Ending use of test pattern.")
                self.logger.info("Ending test lava.%s (%s), duration %.02f",
                                 self.definition, uuid,
                                 time.time() - self.start)
                self.logger.results({
                    "definition": "lava",
                    "case": self.definition,
                    "uuid": uuid,
                    "duration": "%.02f" % (time.time() - self.start),
                    "result": "pass"
                })
                self.start = None
            elif name == "TESTCASE":
                try:
                    data = handle_testcase(params)
                    # get the fixup from the pattern_dict
                    res = self.signal_match.match(data, fixupdict=self.pattern.fixupdict())
                except (JobError, TestError) as exc:
                    self.logger.error(str(exc))
                    return True

                p_res = self.data["test"][
                    self.signal_director.test_uuid
                ].setdefault("results", OrderedDict())

                # prevent losing data in the update
                # FIXME: support parameters and retries
                if res["test_case_id"] in p_res:
                    raise JobError(
                        "Duplicate test_case_id in results: %s",
                        res["test_case_id"])
                # turn the result dict inside out to get the unique
                # test_case_id/testset_name as key and result as value
                res_data = {
                    'definition': self.definition,
                    'case': res["test_case_id"],
                    'result': res["result"]
                }
                # check for measurements
                if 'measurement' in res:
                    res_data['measurement'] = res['measurement']
                    if 'units' in res:
                        res_data['units'] = res['units']

                if self.testset_name:
                    res_data['set'] = self.testset_name
                    self.report[res['test_case_id']] = {
                        'set': self.testset_name,
                        'result': res['result']
                    }
                else:
                    self.report[res['test_case_id']] = res['result']
                # Send the results back
                self.logger.results(res_data)

            elif name == "TESTSET":
                action = params.pop(0)
                if action == "START":
                    name = "testset_" + action.lower()
                    try:
                        self.testset_name = params[0]
                    except IndexError:
                        raise JobError("Test set declared without a name")
                    self.logger.info("Starting test_set %s", self.testset_name)
                elif action == "STOP":
                    self.logger.info("Closing test_set %s", self.testset_name)
                    self.testset_name = None
                    name = "testset_" + action.lower()

            try:
                self.signal_director.signal(name, params)
            except KeyboardInterrupt:
                raise KeyboardInterrupt
            ret_val = True

        elif event == "test_case":
            match = test_connection.match
            if match is pexpect.TIMEOUT:
                self.logger.warning("err: lava_test_shell has timed out (test_case)")
            else:
                res = self.signal_match.match(match.groupdict())
                self.logger.debug("outer_loop_result: %s" % res)
                ret_val = True

        elif event == 'test_case_result':
            res = test_connection.match.groupdict()
            if res:
                res_data = {
                    'definition': self.definition,
                    'case': res["test_case_id"],
                    'result': res["result"]
                }
                # check for measurements
                if 'measurement' in res:
                    res_data['measurement'] = res['measurement']
                    if 'units' in res:
                        res_data['units'] = res['units']

                self.logger.results(res_data)
                self.report[res["test_case_id"]] = res["result"]
            ret_val = True

        return ret_val

    def _keep_running(self, test_connection, timeout, check_char):
        if 'test_case_results' in self.patterns:
            self.logger.info("Test case result pattern: %r" % self.patterns['test_case_results'])
        retval = test_connection.expect(list(self.patterns.values()), timeout=timeout)
        return self.check_patterns(list(self.patterns.keys())[retval], test_connection, check_char)

    class SignalDirector(object):

        # FIXME: create proxy handlers
        def __init__(self, protocol=None):
            """
            Base SignalDirector for singlenode jobs.
            MultiNode and LMP jobs need to create a suitable derived class as both also require
            changes equivalent to the old _keep_running functionality.

            SignalDirector is the link between the Action and the Connection. The Action uses
            the SignalDirector to interact with the I/O over the Connection.
            """
            self._cur_handler = BaseSignalHandler(protocol)
            self.protocol = protocol  # communicate externally over the protocol API
            self.connection = None  # communicate with the device
            self.logger = logging.getLogger("dispatcher")
            self.test_uuid = None

        def setup(self, parameters):
            """
            Allows the parent Action to pass extra data to a customised SignalDirector
            """
            pass

        def signal(self, name, params):
            handler = getattr(self, "_on_" + name.lower(), None)
            if not handler and self._cur_handler:
                handler = self._cur_handler.custom_signal
                params = [name] + list(params)
            if handler:
                try:
                    # The alternative here is to drop the getattr and have a long if:elif:elif:else.
                    # Without python support for switch, this gets harder to read than using
                    # a getattr lookup for the callable (codehelp). So disable checkers:
                    # noinspection PyCallingNonCallable
                    handler(*params)
                except KeyboardInterrupt:
                    raise KeyboardInterrupt
                except TypeError as exc:
                    # handle serial corruption which can overlap kernel messages onto test output.
                    self.logger.exception(str(exc))
                except JobError as exc:
                    self.logger.error("job error: handling signal %s failed: %s", name, exc)
                    return False
                return True

        def postprocess_bundle(self, bundle):
            pass

        def _on_testset_start(self, set_name):
            pass

        def _on_testset_stop(self):
            pass

        def _on_startrun(self, test_run_id, uuid):  # pylint: disable=unused-argument
            """
            runsh.write('echo "<LAVA_SIGNAL_STARTRUN $TESTRUN_ID $UUID>"\n')
            """
            self._cur_handler = None
            if self._cur_handler:
                self._cur_handler.start()

        def _on_endrun(self, test_run_id, uuid):  # pylint: disable=unused-argument
            if self._cur_handler:
                self._cur_handler.end()

        def _on_starttc(self, test_case_id):
            if self._cur_handler:
                self._cur_handler.starttc(test_case_id)

        def _on_endtc(self, test_case_id):
            if self._cur_handler:
                self._cur_handler.endtc(test_case_id)
