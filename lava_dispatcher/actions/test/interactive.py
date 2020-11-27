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

import pexpect
import time
import json

from lava_common.decorators import nottest
from lava_common.exceptions import (
    ConnectionClosedError,
    InfrastructureError,
    JobError,
    LAVATimeoutError,
    TestError,
)
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.logical import LavaTest, RetryAction
from lava_dispatcher.protocols.multinode import MultinodeProtocol
from lava_dispatcher.utils.strings import substitute


@nottest
class TestInteractive(LavaTest):
    """
    TestInteractive Strategy object
    """

    @classmethod
    def action(cls, parameters):
        return TestInteractiveRetry()

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
    def needs_deployment_data(cls, parameters):
        return False

    @classmethod
    def needs_overlay(cls, parameters):
        return False

    @classmethod
    def has_shell(cls, parameters):
        return False


@nottest
class TestInteractiveRetry(RetryAction):

    name = "lava-test-interactive-retry"
    description = "Retry wrapper for lava-test-interactive"
    summary = "Retry support for Lava Test Interactive"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(TestInteractiveAction())


@nottest
class TestInteractiveAction(Action):

    name = "lava-test-interactive"
    description = "Executing lava-test-interactive"
    summary = "Lava Test Interactive"
    timeout_exception = LAVATimeoutError

    def populate(self, parameters):
        super().populate(parameters)
        proto = [
            protocol
            for protocol in self.job.protocols
            if protocol.name == MultinodeProtocol.name
        ]
        self.multinode_proto = proto[0] if proto else None

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)

        if not connection:
            raise ConnectionClosedError("Connection closed")

        # Get substitutions from bootloader-overlay
        substitutions = self.get_namespace_data(
            action="bootloader-overlay", label="u-boot", key="substitutions"
        )
        if substitutions is None:
            substitutions = {}

        # Loop on all scripts
        for script in self.parameters["interactive"]:
            start = time.time()

            # Set the connection prompts
            connection.prompt_str = script["prompts"]

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

        return connection

    def run_script(self, test_connection, script, substitutions):
        prompts = script["prompts"]  # TODO: allow to change the prompts?
        cmds = script["script"]

        def multinode2subst(msg):
            for role_id, data in msg.items():
                for k, v in data.items():
                    substitutions["{%s}" % k] = v

        for index, cmd in enumerate(cmds):
            if "delay" in cmd:
                self.logger.info("Delaying for %ss", cmd["delay"])
                time.sleep(cmd["delay"])
                continue
            elif "lava-send" in cmd:
                payload = {}
                line = substitute([cmd["lava-send"]], substitutions)[0]
                parts = line.split()
                for p in parts[1:]:
                    k, v = p.split("=", 1)
                    payload[k] = v
                res = self.multinode_proto.request_send(parts[0], payload)
                self.logger.info("send result: %r", res)
                continue
            elif "lava-wait" in cmd:
                self.multinode_proto.set_timeout(self.timeout.duration)
                res = self.multinode_proto.request_wait(cmd["lava-wait"])
                self.logger.info("wait result: %r", res)
                res = json.loads(res)
                # Capture any payload key-value pairs as possible substitutions.
                multinode2subst(res["message"])
                continue
            elif "lava-wait-all" in cmd:
                parts = cmd["lava-wait-all"].split()
                if not (1 <= len(parts) <= 2):
                    raise JobError(
                        "lava-wait-all expects 1 or 2 params, got: %s" % parts
                    )
                role = None
                if len(parts) > 1:
                    key, role = parts[1].split("=", 1)
                    if key != "role":
                        raise JobError(
                            "lava-wait-all 2nd param must be role=<rolename>, got: %s"
                            % key
                        )
                self.multinode_proto.set_timeout(self.timeout.duration)
                res = self.multinode_proto.request_wait_all(parts[0], role)
                self.logger.info("wait-all result: %r", res)
                res = json.loads(res)
                if res["response"] == "nack":
                    raise TestError(
                        "Nack reply from coordinator for wait-all (deadlock detected?)"
                    )
                # Capture any payload key-value pairs as possible substitutions.
                multinode2subst(res["message"])
                continue
            elif "lava-sync" in cmd:
                self.multinode_proto.set_timeout(self.timeout.duration)
                res = self.multinode_proto.request_sync(cmd["lava-sync"])
                self.logger.info("sync result: %r", res)
                continue

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
                    if script.get("echo") == "discard":
                        echo = test_connection.readline()
                        self.logger.debug("Ignoring echo: %r", echo)

                failures = [p["message"] for p in cmd.get("failures", [])]
                successes = [p["message"] for p in cmd.get("successes", [])]
                wait_for_prompt = cmd.get("wait_for_prompt", True)

                expect = prompts + failures + successes
                self.logger.debug("Waiting for '%s'", "', '".join(expect))
                ret = test_connection.expect(expect, timeout=self.timeout.duration)

                match = expect[ret]
                # Is this a prompt?
                if match in prompts:
                    # If we match a prompt while successes are defined, that's an error
                    if successes:
                        self.logger.error(
                            "Matched a prompt (was expecting a success): '%s'", match
                        )
                    else:
                        self.logger.debug("Matched a prompt: '%s'", match)
                        result["result"] = "pass"
                else:
                    if match in failures:
                        failure = cmd["failures"][ret - len(prompts)]
                        self.logger.error("Matched a failure: '%s'", match)
                        if "exception" in failure:
                            self.raise_exception(
                                failure["exception"], failure.get("error", match)
                            )
                        # Wait for the prompt to send the next command
                        if wait_for_prompt:
                            test_connection.expect(prompts)
                    else:
                        groups = test_connection.match.groupdict()
                        if groups:
                            self.logger.info(
                                "Matched a success: '%s' (groups: %s)", match, groups
                            )
                        else:
                            self.logger.info("Matched a success: '%s'", match)
                        for k, v in groups.items():
                            substitutions["{%s}" % k] = v
                        # Wait for the prompt to send the next command
                        if wait_for_prompt:
                            test_connection.expect(prompts)
                        result["result"] = "pass"

                # If the command is not named, a failure is fatal
                if "name" not in cmd and result["result"] == "fail":
                    raise TestError("Failed to run command '%s'" % command)
            except pexpect.TIMEOUT:
                raise LAVATimeoutError("interactive connection timed out")
            except pexpect.EOF:
                raise ConnectionClosedError("Connection closed")
            finally:
                # If the command is named, record the result
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
            raise JobError("Unknown exception '%s' with '%s'" % (exc_name, exc_message))
