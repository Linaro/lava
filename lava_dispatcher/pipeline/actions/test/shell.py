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
    Pipeline,
    JobError,
    TestError,
    LAVABug,
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
    DEFAULT_V1_PATTERN,
    DEFAULT_V1_FIXUP,
)
from lava_dispatcher.pipeline.utils.udev import (
    get_udev_devices,
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
        """
        super(TestShellAction, self).run(connection, max_end_time, args)

        # Get the connection, specific to this namespace
        connection = self.get_namespace_data(
            action='shared', label='shared', key='connection', deepcopy=False)
        if not connection:
            raise LAVABug("No connection retrieved from namespace data")

        self.signal_director.connection = connection

        pattern_dict = {self.pattern.name: self.pattern}
        # pattern dictionary is the lookup from the STARTRUN to the parse pattern.
        self.set_namespace_data(action=self.name, label=self.name, key='pattern_dictionary', value=pattern_dict)
        if self.character_delay > 0:
            self.logger.debug("Using a character delay of %i (ms)", self.character_delay)

        if not connection.prompt_str:
            connection.prompt_str = [self.job.device.get_constant(
                'default-shell-prompt')]
            # FIXME: This should be logged whenever prompt_str is changed, by the connection object.
            self.logger.debug("Setting default test shell prompt %s", connection.prompt_str)
        connection.timeout = self.connection_timeout
        # force an initial prompt - not all shells will respond without an excuse.
        connection.sendline(connection.check_char)
        self.wait(connection)

        # use the string instead of self.name so that inheriting classes (like multinode)
        # still pick up the correct command.
        running = self.parameters['stage']
        pre_command_list = self.get_namespace_data(action='test', label="lava-test-shell", key='pre-command-list')
        lava_test_results_dir = self.get_namespace_data(
            action='test', label='results', key='lava_test_results_dir')
        lava_test_sh_cmd = self.get_namespace_data(action='test', label='shared', key='lava_test_sh_cmd')

        if pre_command_list and running == 0:
            for command in pre_command_list:
                connection.sendline(command, delay=self.character_delay)

        self.logger.debug("Using %s" % lava_test_results_dir)
        connection.sendline('ls -l %s/' % lava_test_results_dir, delay=self.character_delay)
        if lava_test_sh_cmd:
            connection.sendline('export SHELL=%s' % lava_test_sh_cmd, delay=self.character_delay)

        try:
            feedbacks = []
            for feedback_ns in self.data.keys():
                if feedback_ns == self.parameters.get('namespace'):
                    continue
                feedback_connection = self.get_namespace_data(
                    action='shared', label='shared', key='connection',
                    deepcopy=False, parameters={"namespace": feedback_ns})
                if feedback_connection:
                    self.logger.debug("Will listen to feedbacks from '%s' for 1 second",
                                      feedback_ns)
                    feedbacks.append((feedback_ns, feedback_connection))

            with connection.test_connection() as test_connection:
                # the structure of lava-test-runner means that there is just one TestAction and it must run all definitions
                test_connection.sendline(
                    "%s/bin/lava-test-runner %s/%s" % (
                        lava_test_results_dir,
                        lava_test_results_dir,
                        running),
                    delay=self.character_delay)

                test_connection.timeout = min(self.timeout.duration, self.connection_timeout.duration)
                self.logger.info("Test shell timeout: %ds (minimum of the action and connection timeout)",
                                 test_connection.timeout)

                # Because of the feedbacks, we use a small value for the
                # timeout.  This allows to grab feedback regularly.
                last_check = time.time()
                while self._keep_running(test_connection, test_connection.timeout, connection.check_char):
                    # Only grab the feedbacks every test_connection.timeout
                    if feedbacks and time.time() - last_check > test_connection.timeout:
                        for feedback in feedbacks:
                            self.logger.debug("Listening to namespace '%s'", feedback[0])
                            # The timeout is really small because the goal is only
                            # to clean the buffer of the feedback connections:
                            # the characters are already in the buffer.
                            # With an higher timeout, this can have a big impact on
                            # the performances of the overall loop.
                            feedback[1].listen_feedback(timeout=1)
                            self.logger.debug("Listening to namespace '%s' done", feedback[0])
                        last_check = time.time()
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
        testdef_commit = self.get_namespace_data(
            action='test', label=uuid, key='commit-id')
        if testdef_commit:
            self.current_run.update({
                'commit_id': testdef_commit
            })

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
        res = {
            "definition": "lava",
            "case": self.definition,
            "uuid": uuid,
            'repository': self.get_namespace_data(
                action='test', label=uuid, key='repository'),
            'path': self.get_namespace_data(
                action='test', label=uuid, key='path'),
            "duration": "%.02f" % (time.time() - self.start),
            "result": "pass"
        }
        revision = self.get_namespace_data(action='test', label=uuid, key='revision')
        res['revision'] = revision if revision else 'unspecified'
        res['namespace'] = self.parameters['namespace']
        commit_id = self.get_namespace_data(action='test', label=uuid, key='commit-id')
        if commit_id:
            res['commit_id'] = commit_id

        self.logger.results(res)  # pylint: disable=no-member
        self.start = None

    def _replace_invalid_url_characters(self, slug):
        new_slug = re.sub('[^0-9a-zA-Z-_]+', '_', slug)
        if new_slug != slug:
            self.logger.warning("'%s' contains invalid slug characters and will be replaced with '%s'" % (slug, new_slug))
        return new_slug

    @nottest
    def signal_test_case(self, params):
        try:
            data = handle_testcase(params)
            if "test_case_id" in data:
                # Replace invalid characters in test_case_id with '_'.
                data["test_case_id"] = self._replace_invalid_url_characters(
                    data["test_case_id"])

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
        self.logger.info(
            "Get USB device(s) using: %s",
            yaml.dump(self.job.device.get('device_info', [])).strip()
        )
        device_paths = get_udev_devices(self.job, self.logger)
        if not device_paths:
            self.logger.warning("No USB devices added to the LXC.")
            return False
        for device in device_paths:
            lxc_cmd = ['lxc-device', '-n', lxc_name, 'add', device]
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
            test_case_id = "%s" % res['test_case_id'].replace('/', '_')
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
            # allow feedback in long runs
            ret_val = True

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
