# Copyright (C) 2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
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

from nose.tools import nottest
import time

from lava_common.exceptions import InfrastructureError, JobError, TestError
from lava_dispatcher.action import Pipeline
from lava_dispatcher.actions.test import TestAction
from lava_dispatcher.logical import LavaTest, RetryAction
from lava_dispatcher.utils.strings import substitute


@nottest
class TestInteractive(LavaTest):
    """
    TestInteractive Strategy object
    """

    def __init__(self, parent, parameters):
        super().__init__(parent)
        self.action = TestInteractiveRetry()
        self.action.job = self.job
        self.action.section = self.action_type
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        required_parms = ["name", "prompts", "script"]
        if "interactive" in parameters:
            for script in parameters["interactive"]:
                if not all([x for x in required_parms if x in script]):
                    return (
                        False,
                        "missing a required parameter from %s" % required_parms,
                    )
            return True, "accepted"
        return False, '"interactive" not in parameters'

    @classmethod
    def needs_deployment_data(cls):
        return False

    @classmethod
    def needs_overlay(cls):
        return False

    @classmethod
    def has_shell(cls):
        return False


@nottest
class TestInteractiveRetry(RetryAction):

    name = "lava-test-interactive-retry"
    description = "Retry wrapper for lava-test-interactive"
    summary = "Retry support for Lava Test Interactive"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(
            parent=self, job=self.job, parameters=parameters
        )
        self.internal_pipeline.add_action(TestInteractiveAction())


@nottest
class TestInteractiveAction(TestAction):
    name = "lava-test-interactive"
    description = "Executing lava-test-interactive"
    summary = "Lava Test Interactive"

    def __init__(self):
        super().__init__()

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)

        if not connection:
            raise InfrastructureError("Connection closed")

        # Get substitutions from bootloader-overlay
        substitutions = self.get_namespace_data(
            action="bootloader-overlay", label="u-boot", key="substitutions"
        )
        if substitutions is None:
            substitutions = {}

        # Loop on all scripts
        for script in self.parameters["interactive"]:
            start = time.time()
            result = {
                "definition": "lava",
                "case": "%s_%s" % (self.parameters["stage"], script["name"]),
                "result": "fail",
            }
            try:
                with connection.test_connection() as test_connection:
                    self.run_script(test_connection, script, substitutions)
                result["result"] = "pass"
            finally:
                # Log the current script result (even in case of error)
                result["duration"] = "%.02f" % (time.time() - start)
                self.logger.results(result)

            # Set the connection prompts
            connection.prompt_str = script["prompts"]

        return connection

    def run_script(self, test_connection, script, substitutions):
        prompts = script["prompts"]  # TODO: allow to change the prompts?
        cmds = script["script"]

        for (index, cmd) in zip(range(0, len(cmds)), cmds):
            command = cmd["command"]
            if command is not None:
                command = substitute([cmd["command"]], substitutions)[0]
            start = time.time()
            result = {
                "definition": "%s_%s" % (self.parameters["stage"], script["name"]),
                "case": cmd.get("name", ""),
                "result": "fail",
            }

            try:
                # If the command is None, we should not send anything, just
                # wait.
                if command is None:
                    self.logger.info("Sending nothing, waiting")
                else:
                    self.logger.info("Sending '%s'", command)
                    test_connection.sendline(command, delay=self.character_delay)

                expect = prompts + [p["message"] for p in cmd.get("patterns", [])]
                self.logger.debug("Waiting for '%s'", "', '".join(expect))
                ret = test_connection.expect(expect, timeout=self.timeout.duration)

                # Is this a prompt?
                if ret < len(prompts):
                    self.logger.debug("Matched a prompt: '%s'", prompts[ret])
                    result["result"] = "pass"
                else:
                    pattern = cmd["patterns"][ret - len(prompts)]
                    if pattern["result"] == "failure":
                        self.logger.error("Matched a failure: '%s'", expect[ret])
                        if "exception" in pattern:
                            self.raise_exception(
                                pattern["exception"], pattern.get("error", expect[ret])
                            )
                    elif pattern["result"] == "success":
                        self.logger.info("Matched a success: '%s'", expect[ret])
                        # Wait for the prompt to send the next command
                        # Except for the last loop iteration
                        if index + 1 < len(cmds):
                            test_connection.expect(prompts)
                        result["result"] = "pass"
                    else:
                        raise JobError("Unknown result '%s'" % pattern["result"])
            finally:
                if "name" in cmd:
                    result["duration"] = "%.02f" % (time.time() - start)
                    self.logger.results(result)

    def raise_exception(self, exc_name, exc_message):
        if exc_name == "InfrastructureError":
            raise InfrastructureError(exc_message)
        elif exc_name == "JobError":
            raise JobError(exc_message)
        elif exc_name == "TestError":
            raise TestError(exc_message)
        else:
            raise JobError("Unknow exception '%s' with '%s'" % (exc_name, exc_message))
