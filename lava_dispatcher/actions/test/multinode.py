# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from lava_common.exceptions import MultinodeProtocolTimeoutError, TestError
from lava_common.timeout import Timeout
from lava_dispatcher.action import Action
from lava_dispatcher.actions.test.shell import TestShellAction
from lava_dispatcher.protocols.multinode import MultinodeProtocol

if TYPE_CHECKING:
    from lava_dispatcher.job import Job

# TODO: This is a workaround allowing to run multinode jobs with "monitors"
# and "interactive" test actions - simple scenarios, without cross-device
# synchronization. Properly handling test action class selection (in a
# "pluggable" vs hardcoded way) would apparently require changes to
# logical.Deployment class. And supporting cross-device synchronization
# would likely require moving the corresponding logic to some base class,
# from which individual test action implementations would inherit. In the
# meantime, this is a small and localized workaround enabling multinode
# for those test actions ahead of heavy refactors above.


class MultinodeMixin(Action):
    timeout_exception = TestError

    def __init__(self, job: Job):
        super().__init__(job)
        self.multinode_dict = {"multinode": r"<LAVA_MULTI_NODE> <LAVA_(\S+) ([^>]+)>"}

    def validate(self):
        super().validate()
        # MultinodeProtocol is required, others can be optional
        if MultinodeProtocol.name not in [
            protocol.name for protocol in self.job.protocols
        ]:
            self.errors = "Invalid job - missing protocol"
        if MultinodeProtocol.name not in [protocol.name for protocol in self.protocols]:
            self.errors = "Missing protocol"
        if not self.valid:
            self.errors = "Invalid base class TestAction"
            return
        self.patterns.update(self.multinode_dict)
        self.signal_director.setup(
            self.parameters, character_delay=self.character_delay
        )

    def _reset_patterns(self):
        super()._reset_patterns()
        self.patterns.update(self.multinode_dict)

    def populate(self, parameters):
        """
        Select the appropriate protocol supported by this action from the list available from the job
        """
        self.protocols = [
            protocol
            for protocol in self.job.protocols
            if protocol.name == MultinodeProtocol.name
        ]
        self.signal_director = self.SignalDirector(self.job, self.protocols[0])

    def check_patterns(self, event, test_connection):
        """
        Calls the parent check_patterns first, then checks for subclass pattern.
        """
        ret = super().check_patterns(event, test_connection)
        if event == "multinode":
            name, params = test_connection.match.groups()
            self.logger.debug("Received Multi_Node API <LAVA_%s>" % name)
            if name == "SEND":
                params = re.split(r"\s+(?=\w+(?:=))", params)
            else:
                params = params.split()
            test_case_name = "%s-%s" % (name, params[0])  # use the messageID
            self.logger.debug("messageID: %s", test_case_name)

            test_case_params = "TEST_CASE_ID=multinode-{} RESULT={}"
            try:
                ret = self.signal_director.signal(name, params)
            except MultinodeProtocolTimeoutError as exc:
                self.logger.warning(
                    "Sync error in %s signal: %s %s" % (event, exc, name)
                )

                self.signal_test_case(
                    test_case_params.format(test_case_name.lower(), "fail").split()
                )

                return False

            self.signal_test_case(
                test_case_params.format(test_case_name.lower(), "pass").split()
            )
            return ret
        return ret

    class SignalDirector(TestShellAction.SignalDirector):
        def __init__(self, job: Job, protocol):
            super().__init__(job, protocol)
            self.character_delay = 0
            self.base_message = {}

        def setup(self, parameters, character_delay=0):
            """
            Retrieve the poll_timeout from the protocol parameters which are set after init.
            """
            super().setup(parameters)
            if MultinodeProtocol.name not in parameters:
                return
            if "timeout" in parameters[MultinodeProtocol.name]:
                self.base_message = {
                    "timeout": Timeout.parse(
                        parameters[MultinodeProtocol.name]["timeout"]
                    )
                }
            self.character_delay = character_delay

        def _on_send(self, *args):
            self.logger.debug("%s lava-send" % MultinodeProtocol.name)
            arg_length = len(args)
            if arg_length == 1:
                msg = {"request": "lava_send", "messageID": args[0], "message": {}}
            else:
                message_id = args[0]
                remainder = args[1:arg_length]
                self.logger.debug("%d key value pair(s) to be sent." % len(remainder))
                data = {}
                for message in remainder:
                    detail = str.split(message, "=", maxsplit=1)
                    if len(detail) == 2:
                        data[detail[0]] = detail[1]
                msg = {"request": "lava_send", "messageID": message_id, "message": data}

            msg.update(self.base_message)
            self.logger.debug(str("Handling signal <LAVA_SEND %s>" % json.dumps(msg)))
            reply = self.protocol(msg)
            if reply == "nack":
                # FIXME: does this deserve an automatic retry? Does it actually happen?
                raise TestError("Coordinator was unable to accept LAVA_SEND")

        def _on_sync(self, message_id):
            self.logger.debug("Handling signal <LAVA_SYNC %s>" % message_id)
            msg = {"request": "lava_sync", "messageID": message_id, "message": None}
            msg.update(self.base_message)
            reply = self.protocol(msg)
            if reply == "nack":
                message_str = " nack"
            else:
                message_str = ""
            self.connection.sendline(
                "<LAVA_SYNC_COMPLETE%s>" % message_str, delay=self.character_delay
            )
            self.connection.sendline("\n")

        def _on_wait(self, message_id):
            self.logger.debug("Handling signal <LAVA_WAIT %s>" % message_id)
            msg = {"request": "lava_wait", "messageID": message_id, "message": None}
            msg.update(self.base_message)
            reply = self.protocol(msg)
            self.logger.debug("reply=%s" % reply)
            message_str = ""
            if reply == "nack":
                message_str = " nack"
            else:
                for target, messages in reply.items():
                    for key, value in messages.items():
                        message_str += " %s:%s=%s" % (target, key, value)
            self.connection.sendline(
                "<LAVA_WAIT_COMPLETE%s>" % message_str, delay=self.character_delay
            )
            self.connection.sendline("\n")

        def _on_wait_all(self, message_id, role=None):
            self.logger.debug("Handling signal <LAVA_WAIT_ALL %s>" % message_id)
            msg = {"request": "lava_wait_all", "messageID": message_id, "role": role}
            msg.update(self.base_message)
            reply = self.protocol(msg)
            message_str = ""
            if reply == "nack":
                message_str = " nack"
            else:
                # the reply format is like this :
                # "{target:{key1:value, key2:value2, key3:value3},
                #  target2:{key1:value, key2:value2, key3:value3}}"
                for target, messages in reply.items():
                    for key, value in messages.items():
                        message_str += " %s:%s=%s" % (target, key, value)
            self.connection.sendline(
                "<LAVA_WAIT_ALL_COMPLETE%s>" % message_str, delay=self.character_delay
            )
            self.connection.sendline("\n")


class MultinodeTestAction(MultinodeMixin, TestShellAction):
    name = "multinode-test"
    description = "Executing lava-test-runner"
    summary = "Multinode Lava Test Shell"
