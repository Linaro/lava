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

import os
import re
import sys
import time
import yaml
import decimal
import logging
import pexpect
from nose.tools import nottest
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
from lava_dispatcher.pipeline.protocols.lxc import LxcProtocol
from lava_dispatcher.pipeline.utils.constants import (
    DEFAULT_SHELL_PROMPT,
    DEFAULT_V1_PATTERN,
    DEFAULT_V1_FIXUP,
)
from lava_dispatcher.pipeline.utils.udev import (
    get_usb_devices,
    usb_device_wait,
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
        return ('definition' in parameters) or ('definitions' in parameters)

    @classmethod
    def needs_deployment_data(cls):
        return True

    @classmethod
    def needs_overlay(cls):
        return True

    @classmethod
    def has_shell(cls):
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
        self.testset_name = None
        self.report = {}
        self.start = None
        self.testdef_dict = {}
        # noinspection PyTypeChecker
        self.pattern = PatternFixup(testdef=None, count=0)
        self.current_run = None

    def _reset_patterns(self):
        # Extend the list of patterns when creating subclasses.
        self.patterns = {
            "exit": "<LAVA_TEST_RUNNER>: exiting",
            "error": "<LAVA_TEST_RUNNER>: ([^ ]+) installer failed, skipping",
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

    def run(self, connection, max_end_time, args=None):
        """
        Common run function for subclasses which define custom patterns
        boot-result is a simple sanity test and only supports the most recent boot
        just to allow the test action to know if something has booted. Failed boots will timeout.
        A missing boot-result could be a missing deployment for some actions.
        """
        # Sanity test: could be a missing deployment for some actions
        res = self.get_namespace_data(action='boot', label='shared', key='boot-result')
        if not res:
            raise LAVABug("No boot action result found")
        super(TestShellAction, self).run(connection, max_end_time, args)

        # Get the connection, specific to this namespace
        connection = self.get_namespace_data(
            action='shared', label='shared', key='connection', deepcopy=False)

        res = self.get_namespace_data(action='boot', label='shared', key='boot-result')
        if res != "success":
            self.logger.debug("Skipping test definitions - previous boot attempt was not successful.")
            self.results.update({self.name: "skipped"})
            # FIXME: with predictable UID, could set each test definition metadata to "skipped"
            return connection

        if not connection:
            raise InfrastructureError("Connection closed")

        self.signal_director.connection = connection

        pattern_dict = {self.pattern.name: self.pattern}
        # pattern dictionary is the lookup from the STARTRUN to the parse pattern.
        self.set_namespace_data(action=self.name, label=self.name, key='pattern_dictionary', value=pattern_dict)

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
        stage = self.get_namespace_data(action='test-definition', label='lava-test-shell', key='stages')
        pre_command_list = self.get_namespace_data(action='test', label="lava-test-shell", key='pre-command-list')
        lava_test_results_dir = self.get_namespace_data(
            action='test', label='results', key='lava_test_results_dir')
        lava_test_sh_cmd = self.get_namespace_data(action='test', label='shared', key='lava_test_sh_cmd')

        for running in xrange(stage + 1):
            if pre_command_list and running == 0:
                for command in pre_command_list:
                    connection.sendline(command)

            self.logger.debug("Using %s" % lava_test_results_dir)
            connection.sendline('ls -l %s/' % lava_test_results_dir)
            if lava_test_sh_cmd:
                connection.sendline('export SHELL=%s' % lava_test_sh_cmd)

            try:
                with connection.test_connection() as test_connection:
                    # the structure of lava-test-runner means that there is just one TestAction and it must run all definitions
                    test_connection.sendline(
                        "%s/bin/lava-test-runner %s/%s" % (
                            lava_test_results_dir,
                            lava_test_results_dir,
                            running),
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
            finally:
                if self.current_run is not None:
                    self.logger.error("Marking unfinished test run as failed")
                    self.current_run["duration"] = "%.02f" % (time.time() - self.start)
                    self.logger.results(self.current_run)  # pylint: disable=no-member
                    self.current_run = None

        # Only print if the report is not empty
        if self.report:
            self.logger.debug(yaml.dump(self.report, default_flow_style=False))
        if self.errors:
            raise TestError(self.errors)
        return connection

    def pattern_error(self, test_connection):
        (testrun, ) = test_connection.match.groups()
        self.logger.error("Unable to start testrun %s. "
                          "Read the log for more details.", testrun)
        self.errors = "Unable to start testrun %s" % testrun
        # This is not accurate but required when exiting.
        self.start = time.time()
        self.current_run = {
            "definition": "lava",
            "case": testrun,
            "result": "fail"
        }
        return True

    def signal_start_run(self, params):
        self.signal_director.test_uuid = params[1]
        self.definition = params[0]
        uuid = params[1]
        self.start = time.time()
        self.logger.info("Starting test lava.%s (%s)", self.definition, uuid)
        # set the pattern for this run from pattern_dict
        testdef_index = self.get_namespace_data(action='test-definition', label='test-definition',
                                                key='testdef_index')
        uuid_list = self.get_namespace_data(action='repo-action', label='repo-action', key='uuid-list')
        for (key, value) in enumerate(testdef_index):
            if self.definition == "%s_%s" % (key, value):
                pattern_dict = self.get_namespace_data(action='test', label=uuid_list[key], key='testdef_pattern')
                pattern = pattern_dict['testdef_pattern']['pattern']
                fixup = pattern_dict['testdef_pattern']['fixupdict']
                self.patterns.update({'test_case_result': re.compile(pattern, re.M)})
                self.pattern.update(pattern, fixup)
                self.logger.info("Enabling test definition pattern %r" % pattern)
                self.logger.info("Enabling test definition fixup %r" % self.pattern.fixup)
        self.current_run = {
            "definition": "lava",
            "case": self.definition,
            "uuid": uuid,
            "result": "fail"
        }

    def signal_end_run(self, params):
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
        self.current_run = None
        self.logger.results({  # pylint: disable=no-member
            "definition": "lava",
            "case": self.definition,
            "uuid": uuid,
            "duration": "%.02f" % (time.time() - self.start),
            "result": "pass"
        })
        self.start = None

    @nottest
    def signal_test_case(self, params):
        try:
            data = handle_testcase(params)
            # get the fixup from the pattern_dict
            res = self.signal_match.match(data, fixupdict=self.pattern.fixupdict())
        except (JobError, TestError) as exc:
            self.logger.error(str(exc))
            return True

        p_res = self.get_namespace_data(action='test', label=self.signal_director.test_uuid, key='results')
        if not p_res:
            p_res = OrderedDict()
            self.set_namespace_data(
                action='test', label=self.signal_director.test_uuid, key='results', value=p_res)

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
            try:
                measurement = decimal.Decimal(res['measurement'])
            except decimal.InvalidOperation:
                raise TestError("Invalid measurement %s", res['measurement'])
            res_data['measurement'] = measurement
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
        self.logger.results(res_data)  # pylint: disable=no-member

    @nottest
    def signal_test_reference(self, params):
        if len(params) != 3:
            raise TestError("Invalid use of TESTREFERENCE")
        res_dict = {
            'case': params[0],
            'definition': self.definition,
            'result': params[1],
            'reference': params[2],
        }
        if self.testset_name:
            res_dict.update({'set': self.testset_name})
        self.logger.results(res_dict)  # pylint: disable=no-member

    @nottest
    def signal_test_set(self, params):
        name = None
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
        return name

    def signal_lxc_add(self):
        # the lxc namespace may not be accessible here depending on the
        # lava-test-shell action namespace.
        lxc_name = None
        protocols = [protocol for protocol in self.job.protocols if protocol.name == LxcProtocol.name]
        protocol = protocols[0] if protocols else None
        if protocol:
            lxc_name = protocol.lxc_name
        if not lxc_name:
            self.logger.debug("No LXC device requested")
            return False
        self.logger.info("Get USB device(s) ...")
        device_paths = get_usb_devices(self.job)
        for device in device_paths:
            lxc_cmd = ['lxc-device', '-n', lxc_name, 'add',
                       os.path.realpath(device)]
            log = self.run_command(lxc_cmd)
            self.logger.debug(log)
            self.logger.debug("%s: device %s added", lxc_name,
                              device)
        return True

    @nottest
    def pattern_test_case(self, test_connection):
        match = test_connection.match
        if match is pexpect.TIMEOUT:
            self.logger.warning("err: lava_test_shell has timed out (test_case)")
            return False
        res = self.signal_match.match(match.groupdict(), fixupdict=self.pattern.fixupdict())
        self.logger.debug("outer_loop_result: %s" % res)
        return True

    @nottest
    def pattern_test_case_result(self, test_connection):
        res = test_connection.match.groupdict()
        fixupdict = self.pattern.fixupdict()
        if res['result'] in fixupdict:
            res['result'] = fixupdict[res['result']]
        if res:
            # disallow whitespace in test_case_id
            test_case_id = "%s" % res['test_case_id']
            if ' ' in test_case_id.strip():
                self.logger.debug("Skipping invalid test_case_id '%s'", test_case_id.strip())
                return True
            res_data = {
                'definition': self.definition,
                'case': res["test_case_id"],
                'result': res["result"]
            }
            # check for measurements
            if 'measurement' in res:
                try:
                    measurement = decimal.Decimal(res['measurement'])
                except decimal.InvalidOperation:
                    raise TestError("Invalid measurement %s", res['measurement'])
                res_data['measurement'] = measurement
                if 'units' in res:
                    res_data['units'] = res['units']

            self.logger.results(res_data)  # pylint: disable=no-member
            self.report[res["test_case_id"]] = res["result"]
        return True

    def check_patterns(self, event, test_connection, check_char):  # pylint: disable=unused-argument
        """
        Defines the base set of pattern responses.
        Stores the results of testcases inside the TestAction
        Call from subclasses before checking subclass-specific events.
        """
        ret_val = False
        if event == "exit":
            self.logger.info("ok: lava_test_shell seems to have completed")
            self.testset_name = None

        elif event == "error":
            # Parsing is not finished
            ret_val = self.pattern_error(test_connection)

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
                self.signal_start_run(params)
            elif name == "ENDRUN":
                self.signal_end_run(params)
            elif name == "TESTCASE":
                self.signal_test_case(params)
            elif name == "TESTREFERENCE":
                self.signal_test_reference(params)
            elif name == "TESTSET":
                ret = self.signal_test_set(params)
                if ret:
                    name = ret
            elif name == "LXCDEVICEADD":
                self.signal_lxc_add()
            elif name == "LXCDEVICEWAITADD":
                self.logger.info("Waiting for USB device(s) ...")
                usb_device_wait(self.job, device_actions=['add'])

            self.signal_director.signal(name, params)
            ret_val = True

        elif event == "test_case":
            ret_val = self.pattern_test_case(test_connection)
        elif event == 'test_case_result':
            ret_val = self.pattern_test_case_result(test_connection)
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

        # noinspection PyUnusedLocal
        def _on_startrun(self, test_run_id, uuid):  # pylint: disable=unused-argument
            """
            runsh.write('echo "<LAVA_SIGNAL_STARTRUN $TESTRUN_ID $UUID>"\n')
            """
            self._cur_handler = None
            if self._cur_handler:
                self._cur_handler.start()

        # noinspection PyUnusedLocal
        def _on_endrun(self, test_run_id, uuid):  # pylint: disable=unused-argument
            if self._cur_handler:
                self._cur_handler.end()

        def _on_starttc(self, test_case_id):
            if self._cur_handler:
                self._cur_handler.starttc(test_case_id)

        def _on_endtc(self, test_case_id):
            if self._cur_handler:
                self._cur_handler.endtc(test_case_id)
