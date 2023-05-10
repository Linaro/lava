# Copyright (C) 2014-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import decimal
import logging
import re
import time

import pexpect

from lava_common.decorators import nottest
from lava_common.exceptions import (
    ConnectionClosedError,
    JobError,
    LAVATimeoutError,
    TestError,
)
from lava_common.yaml import yaml_safe_dump
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.connection import SignalMatch
from lava_dispatcher.logical import LavaTest, RetryAction


def handle_testcase(params):
    data = {}
    for param in params:
        parts = param.split("=")
        if len(parts) == 2:
            key, value = parts
            key = key.lower()
            data[key] = value
        else:
            raise JobError('Ignoring malformed parameter for signal: "%s". ' % param)
    return data


class TestShell(LavaTest):
    """
    LavaTestShell Strategy object
    """

    @classmethod
    def action(cls, parameters):
        return TestShellRetry()

    @classmethod
    def accepts(cls, device, parameters):
        if "definitions" in parameters:
            return True, "accepted"
        return False, '"definitions" not in parameters'

    @classmethod
    def needs_deployment_data(cls, parameters):
        """Some, not all, deployments will want deployment_data"""
        return True

    @classmethod
    def needs_overlay(cls, parameters):
        return True

    @classmethod
    def has_shell(cls, parameters):
        return True


@nottest
class TestShellRetry(RetryAction):
    name = "lava-test-retry"
    description = "Retry wrapper for lava-test-shell"
    summary = "Retry support for Lava Test Shell"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(TestShellAction())


# FIXME: move to utils and call inside the overlay
class PatternFixup:
    def __init__(self, testdef, count):
        """
        Like all good arrays, the count is expected to start at zero.
        Avoid calling from validate() or populate() - this needs the
        RepoAction to be running.
        """
        super().__init__()
        self.pat = None
        # Use the same default dict from previous LAVA versions to keep
        # compatibility.
        self.fixup = {
            "PASS": "pass",
            "FAIL": "fail",
            "SKIP": "skip",
            "UNKNOWN": "unknown",
        }
        if isinstance(testdef, dict) and "metadata" in testdef:
            self.testdef = testdef
            self.name = "%d_%s" % (count, testdef["metadata"].get("name"))
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
            raise TestError("Error parsing regular expression %r: %s" % (self.pat, exc))
        self.fixup = fixupdict

    def fixupdict(self):
        if "parse" in self.testdef and "fixupdict" in self.testdef["parse"]:
            self.fixup = self.testdef["parse"]["fixupdict"]
        return self.fixup

    def pattern(self):
        if "parse" in self.testdef and "pattern" in self.testdef["parse"]:
            self.pat = self.testdef["parse"]["pattern"]
            if not isinstance(self.pat, str):
                raise TestError(
                    "Unrecognised test parse pattern type: %s" % type(self.pat)
                )
            try:
                self.pat = re.compile(self.pat, re.M)
            except re.error as exc:
                raise TestError(
                    "Error parsing regular expression %r: %s" % (self.pat, exc)
                )
        return self.pat


@nottest
class TestShellAction(Action):
    """
    Sets up and runs the LAVA Test Shell Definition scripts.
    Supports a pre-command-list of operations necessary on the
    booted image before the test shell can be started.
    """

    name = "lava-test-shell"
    description = "Executing lava-test-runner"
    summary = "Lava Test Shell"
    timeout_exception = LAVATimeoutError

    def __init__(self):
        super().__init__()
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
            "exit": "<LAVA_TEST_RUNNER EXIT>",
            "error": "<LAVA_TEST_RUNNER INSTALL_FAIL>",
            "eof": pexpect.EOF,
            "timeout": pexpect.TIMEOUT,
            "signal": r"<LAVA_SIGNAL_(\S+) ([^>]+)>",
        }
        # noinspection PyTypeChecker
        self.pattern = PatternFixup(testdef=None, count=0)

    def validate(self):
        if "definitions" not in self.parameters:
            raise JobError("Missing test 'definitions'")

        for testdef in self.parameters["definitions"]:
            if "repository" not in testdef:
                self.errors = "Repository missing from test definition"
        self._reset_patterns()
        super().validate()

    def run(self, connection, max_end_time):
        """
        Common run function for subclasses which define custom patterns
        """
        super().run(connection, max_end_time)

        # Get the connection, specific to this namespace
        connection_namespace = self.parameters.get("connection-namespace")
        parameters = None
        if self.timeout.can_skip(self.parameters):
            self.logger.info(
                "The timeout has 'skip' enabled. "
                "If this test action block times out, the job will continue at the next action block."
            )

        if connection_namespace:
            self.logger.debug("Using connection namespace: %s", connection_namespace)
            parameters = {"namespace": connection_namespace}
        else:
            parameters = {"namespace": self.parameters.get("namespace", "common")}
            self.logger.debug("Using namespace: %s", parameters["namespace"])
        connection = self.get_namespace_data(
            action="shared",
            label="shared",
            key="connection",
            deepcopy=False,
            parameters=parameters,
        )

        if not connection:
            self.logger.error(
                "No connection to the DUT, Check that a boot action precede test actions"
            )
            if connection_namespace:
                self.logger.error(
                    "Also check actions in namespace %r", connection_namespace
                )
            raise JobError("No connection to the DUT")

        self.signal_director.connection = connection

        pattern_dict = {self.pattern.name: self.pattern}
        # pattern dictionary is the lookup from the STARTRUN to the parse pattern.
        self.set_namespace_data(
            action=self.name,
            label=self.name,
            key="pattern_dictionary",
            value=pattern_dict,
        )
        if self.character_delay > 0:
            self.logger.debug(
                "Using a character delay of %i (ms)", self.character_delay
            )

        if not connection.prompt_str:
            connection.prompt_str = [
                self.job.device.get_constant("default-shell-prompt")
            ]
            # FIXME: This should be logged whenever prompt_str is changed, by the connection object.
            self.logger.debug(
                "Setting default test shell prompt %s", connection.prompt_str
            )
        connection.timeout = self.connection_timeout
        # force an initial prompt - not all shells will respond without an excuse.
        connection.sendline(connection.check_char)
        self.wait(connection)

        # use the string instead of self.name so that inheriting classes (like multinode)
        # still pick up the correct command.
        running = self.parameters["stage"]
        pre_command_list = self.get_namespace_data(
            action="test", label="lava-test-shell", key="pre-command-list"
        )
        lava_test_results_dir = self.get_namespace_data(
            action="test", label="results", key="lava_test_results_dir"
        )
        lava_test_sh_cmd = self.get_namespace_data(
            action="test", label="shared", key="lava_test_sh_cmd"
        )

        # Any errors arising from this command are not checked.
        # If the result of the command means that lava-test-runner cannot be found,
        # this will cause the job to time out as Incomplete.
        if pre_command_list:
            for command in pre_command_list:
                connection.sendline(command, delay=self.character_delay)
                connection.wait()

        if lava_test_results_dir is None:
            raise JobError(
                "Nothing to run. Maybe the 'deploy' stage is missing, "
                "otherwise this is a bug which should be reported."
            )

        self.logger.debug("Using %s" % lava_test_results_dir)
        if lava_test_sh_cmd:
            connection.sendline(
                "export SHELL=%s" % lava_test_sh_cmd, delay=self.character_delay
            )
            connection.wait()

        # source the environment file containing device-specific shell variables
        connection.sendline(
            ". %s/environment" % lava_test_results_dir, delay=self.character_delay
        )
        connection.wait()

        try:
            feedbacks = []
            for feedback_ns in self.data.keys():
                feedback_connection = self.get_namespace_data(
                    action="shared",
                    label="shared",
                    key="connection",
                    deepcopy=False,
                    parameters={"namespace": feedback_ns},
                )
                if feedback_connection == connection:
                    continue
                if feedback_connection:
                    self.logger.debug(
                        "Will listen to feedbacks from '%s' for 1 second", feedback_ns
                    )
                    feedbacks.append((feedback_ns, feedback_connection))

            with connection.test_connection() as test_connection:
                # the structure of lava-test-runner means that there is just one TestAction and it must run all definitions
                test_connection.sendline(
                    "%s/bin/lava-test-runner %s/%s"
                    % (lava_test_results_dir, lava_test_results_dir, running),
                    delay=self.character_delay,
                )

                test_connection.timeout = min(
                    self.timeout.duration, self.connection_timeout.duration
                )
                self.logger.info(
                    "Test shell timeout: %ds (minimum of the action and connection timeout)",
                    test_connection.timeout,
                )

                # Because of the feedbacks, we use a small value for the
                # timeout.  This allows to grab feedback regularly.
                last_check = time.monotonic()
                while self._keep_running(
                    test_connection, test_connection.timeout, connection.check_char
                ):
                    # Only grab the feedbacks every test_connection.timeout
                    if (
                        feedbacks
                        and time.monotonic() - last_check > test_connection.timeout
                    ):
                        for feedback in feedbacks:
                            # The timeout is really small because the goal is only
                            # to clean the buffer of the feedback connections:
                            # the characters are already in the buffer.
                            # With an higher timeout, this can have a big impact on
                            # the performances of the overall loop.
                            bytes_read = feedback[1].listen_feedback(
                                timeout=1, namespace=feedback[0]
                            )
                            if bytes_read > 0:
                                self.logger.debug(
                                    "Listened to connection for namespace '%s' done",
                                    feedback[0],
                                )
                        last_check = time.monotonic()
        finally:
            if self.current_run is not None:
                self.logger.error("Marking unfinished test run as failed")
                self.current_run["duration"] = "%.02f" % (time.monotonic() - self.start)
                self.logger.results(self.current_run)
                self.current_run = None

        # Only print if the report is not empty
        if self.report:
            self.logger.debug(yaml_safe_dump(self.report, default_flow_style=False))
        if self.errors:
            raise TestError(self.errors)
        return connection

    def pattern_error(self):
        stage = self.parameters["stage"]
        self.logger.error(
            "Unable to start stage %s. Read the log for more details.", stage
        )
        self.errors = "Unable to start test stage %s" % stage
        # This is not accurate but required when exiting.
        self.start = time.monotonic()
        self.current_run = {
            "definition": "lava",
            "case": "stage_%d" % stage,
            "result": "fail",
        }
        return True

    def signal_start_run(self, params):
        self.signal_director.test_uuid = params[1]
        self.definition = params[0]
        uuid = params[1]
        self.start = time.monotonic()
        self.logger.info("Starting test lava.%s (%s)", self.definition, uuid)
        # set the pattern for this run from pattern_dict
        testdef_index = self.get_namespace_data(
            action="test-definition", label="test-definition", key="testdef_index"
        )
        uuid_list = self.get_namespace_data(
            action="repo-action", label="repo-action", key="uuid-list"
        )
        for key, value in enumerate(testdef_index):
            if self.definition == "%s_%s" % (key, value):
                pattern_dict = self.get_namespace_data(
                    action="test", label=uuid_list[key], key="testdef_pattern"
                )
                if not pattern_dict:
                    self.logger.info("Skipping test definition patterns.")
                    continue
                pattern = pattern_dict["testdef_pattern"]["pattern"]
                fixup = pattern_dict["testdef_pattern"]["fixupdict"]
                self.patterns.update({"test_case_result": re.compile(pattern, re.M)})
                self.pattern.update(pattern, fixup)
                self.logger.info("Enabling test definition pattern %r" % pattern)
                self.logger.info(
                    "Enabling test definition fixup %r" % self.pattern.fixup
                )
        self.current_run = {
            "definition": "lava",
            "case": self.definition,
            "uuid": uuid,
            "result": "fail",
        }
        testdef_commit = self.get_namespace_data(
            action="test", label=uuid, key="commit-id"
        )
        if testdef_commit:
            self.current_run.update({"commit_id": testdef_commit})

    def signal_end_run(self, params):
        self.definition = params[0]
        uuid = params[1]
        # remove the pattern for this run from pattern_dict
        self._reset_patterns()
        # catch error in ENDRUN being handled without STARTRUN
        if not self.start:
            self.start = time.monotonic()
        self.logger.info("Ending use of test pattern.")
        self.logger.info(
            "Ending test lava.%s (%s), duration %.02f",
            self.definition,
            uuid,
            time.monotonic() - self.start,
        )
        self.current_run = None
        res = {
            "definition": "lava",
            "case": self.definition,
            "uuid": uuid,
            "repository": self.get_namespace_data(
                action="test", label=uuid, key="repository"
            ),
            "path": self.get_namespace_data(action="test", label=uuid, key="path"),
            "duration": "%.02f" % (time.monotonic() - self.start),
            "result": "pass",
        }
        revision = self.get_namespace_data(action="test", label=uuid, key="revision")
        res["revision"] = revision if revision else "unspecified"
        res["namespace"] = self.parameters["namespace"]
        connection_namespace = self.parameters.get("connection_namespace")
        if connection_namespace:
            res["connection-namespace"] = connection_namespace
        commit_id = self.get_namespace_data(action="test", label=uuid, key="commit-id")
        if commit_id:
            res["commit_id"] = commit_id

        self.logger.results(res)
        self.start = None

    @nottest
    def signal_test_case(self, params):
        # If the STARTRUN signal was not received correctly, we cannot continue
        # as the test_uuid is missing.
        # This is only happening when the signal string is split by some kernel messages.
        if self.signal_director.test_uuid is None:
            self.logger.error(
                "Unknown test uuid. The STARTRUN signal for this test action was not received correctly."
            )
            raise TestError("Invalid TESTCASE signal")
        try:
            data = handle_testcase(params)
            # get the fixup from the pattern_dict
            res = self.signal_match.match(data, fixupdict=self.pattern.fixupdict())
        except (JobError, TestError) as exc:
            self.logger.error(str(exc))
            return True

        # turn the result dict inside out to get the unique
        # test_case_id/testset_name as key and result as value
        res_data = {
            "definition": self.definition,
            "case": res["test_case_id"],
            "result": res["result"],
        }
        # check for measurements
        if "measurement" in res:
            try:
                measurement = decimal.Decimal(res["measurement"])
            except decimal.InvalidOperation:
                raise TestError("Invalid measurement %s" % res["measurement"])
            res_data["measurement"] = float(measurement)
            if "units" in res:
                res_data["units"] = res["units"]

        if self.testset_name:
            res_data["set"] = self.testset_name
            self.report[res["test_case_id"]] = {
                "set": self.testset_name,
                "result": res["result"],
            }
        else:
            self.report[res["test_case_id"]] = res["result"]
        # Send the results back
        self.logger.results(res_data)

    @nottest
    def signal_test_reference(self, params):
        if len(params) != 3:
            raise TestError("Invalid use of TESTREFERENCE")
        res_dict = {
            "case": params[0],
            "definition": self.definition,
            "result": params[1],
            "reference": params[2],
        }
        if self.testset_name:
            res_dict.update({"set": self.testset_name})
        self.logger.results(res_dict)

    @nottest
    def signal_test_feedback(self, params):
        feedback_ns = params[0]
        if feedback_ns not in self.data.keys():
            self.logger.error("%s is not a valid namespace")
            return
        self.logger.info("Requesting feedback from namespace: %s", feedback_ns)
        feedback_connection = self.get_namespace_data(
            action="shared",
            label="shared",
            key="connection",
            deepcopy=False,
            parameters={"namespace": feedback_ns},
        )
        feedback_connection.listen_feedback(timeout=1, namespace=feedback_ns)

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

    @nottest
    def pattern_test_case(self, test_connection):
        match = test_connection.match
        if match is pexpect.TIMEOUT:
            self.logger.warning("err: lava_test_shell has timed out (test_case)")
            return False
        res = self.signal_match.match(
            match.groupdict(), fixupdict=self.pattern.fixupdict()
        )
        self.logger.debug("outer_loop_result: %s" % res)
        return True

    @nottest
    def pattern_test_case_result(self, test_connection):
        res = test_connection.match.groupdict()
        fixupdict = self.pattern.fixupdict()
        if fixupdict and res["result"] in fixupdict:
            res["result"] = fixupdict[res["result"]]
        if res:
            # disallow whitespace in test_case_id
            test_case_id = "%s" % res["test_case_id"].replace("/", "_")
            self.logger.marker({"case": res["test_case_id"], "type": "test_case"})
            if " " in test_case_id.strip():
                self.logger.debug(
                    "Skipping invalid test_case_id '%s'", test_case_id.strip()
                )
                return True
            res_data = {
                "definition": self.definition,
                "case": res["test_case_id"],
                "result": res["result"],
            }
            # check for measurements
            if "measurement" in res:
                try:
                    measurement = decimal.Decimal(res["measurement"])
                except decimal.InvalidOperation:
                    raise TestError("Invalid measurement %s" % res["measurement"])
                res_data["measurement"] = float(measurement)
                if "units" in res:
                    res_data["units"] = res["units"]

            self.logger.results(res_data)
            self.report[res["test_case_id"]] = res["result"]
        return True

    def check_patterns(self, event, test_connection, check_char):
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
            ret_val = self.pattern_error()

        elif event == "eof":
            self.testset_name = None
            raise ConnectionClosedError("Connection closed")

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
            elif name == "STARTTC":
                self.logger.marker({"case": params[0], "type": "start_test_case"})
            elif name == "ENDTC":
                self.logger.marker({"case": params[0], "type": "end_test_case"})
            elif name == "TESTCASE":
                self.logger.marker(
                    {
                        "case": params[0].replace("TEST_CASE_ID=", ""),
                        "type": "test_case",
                    }
                )
                self.signal_test_case(params)
            elif name == "TESTFEEDBACK":
                self.signal_test_feedback(params)
            elif name == "TESTREFERENCE":
                self.signal_test_reference(params)
            elif name == "TESTSET":
                ret = self.signal_test_set(params)
                if ret:
                    name = ret
            elif name == "TESTRAISE":
                raise TestError(" ".join(params))
            elif name == "TESTEVENT":
                self.logger.event(" ".join(params))

            self.signal_director.signal(name, params)
            ret_val = True

        elif event == "test_case":
            ret_val = self.pattern_test_case(test_connection)
        elif event == "test_case_result":
            ret_val = self.pattern_test_case_result(test_connection)
        return ret_val

    def _keep_running(self, test_connection, timeout, check_char):
        if "test_case_results" in self.patterns:
            self.logger.info(
                "Test case result pattern: %r" % self.patterns["test_case_results"]
            )
        retval = test_connection.expect(list(self.patterns.values()), timeout=timeout)
        return self.check_patterns(
            list(self.patterns.keys())[retval], test_connection, check_char
        )

    class SignalDirector:
        # FIXME: create proxy handlers
        def __init__(self, protocol=None):
            """
            Base SignalDirector for singlenode jobs.
            MultiNode and LMP jobs need to create a suitable derived class as both also require
            changes equivalent to the old _keep_running functionality.

            SignalDirector is the link between the Action and the Connection. The Action uses
            the SignalDirector to interact with the I/O over the Connection.
            """
            self.protocol = protocol  # communicate externally over the protocol API
            self.connection = None  # communicate with the device
            self.logger = logging.getLogger("dispatcher")
            self.test_uuid = None

        def setup(self, parameters, character_delay=0):
            """
            Allows the parent Action to pass extra data to a customised SignalDirector
            """
            pass

        def signal(self, name, params):
            handler = getattr(self, "_on_" + name.lower(), None)
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
                    raise TestError(
                        "Unable to handle the test shell signal correctly: %s"
                        % str(exc)
                    )
                except JobError as exc:
                    self.logger.error(
                        "job error: handling signal %s failed: %s", name, exc
                    )
                    return False
                return True
