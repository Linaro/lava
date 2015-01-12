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

import logging
import pexpect
from collections import OrderedDict
from lava_dispatcher.pipeline.actions.test import handle_testcase, TestAction
from lava_dispatcher.pipeline.action import (
    InfrastructureError,
    Pipeline,
    JobError,
)
from lava_dispatcher.pipeline.logical import LavaTest, RetryAction
from lava_dispatcher.pipeline.connection import BaseSignalHandler, SignalMatch


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


class TestShellAction(TestAction):

    def __init__(self):
        super(TestShellAction, self).__init__()
        self.description = "Executing lava-test-runner"
        self.summary = "Lava Test Shell"
        self.name = "lava-test-shell"
        self.signal_director = self.SignalDirector(None)  # no default protocol
        self.patterns = {}
        self.match = SignalMatch()
        self.suite = None
        self.testset = None
        self.report = {}

    def validate(self):
        if "test_image_prompts" not in self.job.device:
            self.errors = "Unable to identify test image prompts from device configuration."
        if "definitions" in self.parameters:
            for testdef in self.parameters["definitions"]:
                if "repository" not in testdef:
                    self.errors = "Repository missing from test definition"
        # Extend the list of patterns when creating subclasses.
        self.patterns.update({
            "exit": "<LAVA_TEST_RUNNER>: exiting",
            "eof": pexpect.EOF,
            "timeout": pexpect.TIMEOUT,
            "signal": r"<LAVA_SIGNAL_(\S+) ([^>]+)>",
        })
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

        self.logger.info("Executing test definitions using %s" % connection.name)
        self.logger.debug("Setting default test shell prompt")
        connection.prompt_str = self.job.device["test_image_prompts"]
        self.logger.debug("Setting default timeout: %s" % self.timeout.duration)
        connection.timeout = self.timeout
        self.wait(connection)

        # FIXME: a predictable UID could be calculated from existing data here.
        # instead, uuid is read from the params to set _current_handler
        # FIXME: can only be run once per TestAction, so collate all patterns for all test definitions.
        # (or work out the uuid from the signal params?)

        # FIXME: not being set
        if self.signal_director.test_uuid:
            self.patterns.update({
                "test_case": self.data["test"][self.signal_director.test_uuid]["testdef_pattern"]["pattern"],
            })

        with connection.test_connection() as test_connection:
            # the structure of lava-test-runner means that there is just one TestAction and it must run all definitions
            test_connection.sendline(
                "%s/bin/lava-test-runner %s" % (
                    self.data["lava_test_results_dir"],
                    self.data["lava_test_results_dir"]),
            )

            if self.timeout:
                test_connection.timeout = self.timeout.duration

            while self._keep_running(test_connection, test_connection.timeout):
                pass

        self.logger.debug(self.report)
        return connection

    def check_patterns(self, event, test_connection):
        """
        Defines the base set of pattern responses.
        Stores the results of testcases inside the TestAction
        Call from subclasses before checking subclass-specific events.
        """
        ret_val = False
        if event == "exit":
            self.logger.info("ok: lava_test_shell seems to have completed")

        elif event == "eof":
            self.logger.warning("err: lava_test_shell connection dropped")
            self.errors = "lava_test_shell connection dropped"

        elif event == "timeout":
            # if target.is_booted():
            #    target.reset_boot()
            self.logger.warning("err: lava_test_shell has timed out")
            self.errors = "lava_test_shell has timed out"

        elif event == "signal":
            name, params = test_connection.match.groups()
            self.logger.debug("Received signal: <%s> %s" % (name, params))
            params = params.split()
            if name == "STARTRUN":
                self.signal_director.test_uuid = params[1]
                self.suite = params[0]
                self.logger.debug("Starting test suite: %s" % self.suite)
            #    self._handle_testrun(params)
            elif name == "TESTCASE":
                data = handle_testcase(params)
                res = self.match.match(data)  # FIXME: rename!
                self.logger.debug("res: %s data: %s" % (res, data))
                p_res = self.data["test"][
                    self.signal_director.test_uuid
                ].setdefault("results", OrderedDict())

                # prevent losing data in the update
                # FIXME: support parameters and retries
                if res["test_case_id"] in p_res:
                    raise JobError("Duplicate test_case_id in results: %s", res["test_case_id"])
                # turn the result dict inside out to get the unique test_case_id as key and result as value
                self.logger.results({
                    'testsuite': self.suite,
                    res["test_case_id"]: res["result"]})
                self.report.update({
                    res["test_case_id"]: res["result"]
                })

            try:
                self.signal_director.signal(name, params)
            except KeyboardInterrupt:
                raise KeyboardInterrupt
            # force output in case there was none but minimal content to increase speed.
            test_connection.sendline("#")
            ret_val = True

        elif event == "test_case":
            match = test_connection.match
            if match is pexpect.TIMEOUT:
                # if target.is_booted():
                #    target.reset_boot()
                self.logger.warning("err: lava_test_shell has timed out (test_case)")
            else:
                res = self.match.match(match.groupdict())  # FIXME: rename!
                self.logger.debug("outer_loop_result: %s" % res)
                # self.data["test"][self.signal_director.test_uuid].setdefault("results", {})
                # self.data["test"][self.signal_director.test_uuid]["results"].update({
                #     {res["test_case_id"]: res}
                # })
                ret_val = True

        return ret_val

    def _keep_running(self, test_connection, timeout):
        self.logger.debug("test shell timeout: %d seconds" % timeout)
        retval = test_connection.expect(list(self.patterns.values()), timeout=timeout)
        return self.check_patterns(list(self.patterns.keys())[retval], test_connection)

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
                    handler(*params)  # pylint: disable=star-args
                except KeyboardInterrupt:
                    raise KeyboardInterrupt
                except TypeError as exc:
                    # handle serial corruption which can overlap kernel messages onto test output.
                    self.logger.exception(exc)
                except JobError as exc:
                    self.logger.error("job error: handling signal %s failed: %s", name, exc)
                    return False
                return True

        def postprocess_bundle(self, bundle):
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
