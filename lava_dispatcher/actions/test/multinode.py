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

import json
from lava_dispatcher.actions.test.shell import TestShellAction
from lava_common.timeout import Timeout
from lava_common.exceptions import TestError, MultinodeProtocolTimeoutError
from lava_dispatcher.actions.test import LavaTest
from lava_dispatcher.protocols.multinode import MultinodeProtocol
from .monitor import TestMonitorRetry
from .interactive import TestInteractiveRetry


# TODO: This is a workaround allowing to run multinode jobs with "monitors"
# and "interactive" test actions - simple scenarios, without cross-device
# synchronization. Properly handling test action class selection (in a
# "pluggable" vs hardcoded way) would apparently require changes to
# logical.Deployment class. And supporting cross-device synchronization
# would likely require moving the corresponding logic to some base class,
# from which individual test action implementations would inherit. In the
# meantime, this is a small and localized workaround enabling multinode
# for those test actions ahead of heavy refactors above.
def get_subaction_class(parameters):
    if "monitors" in parameters:
        cls = TestMonitorRetry
    elif "interactive" in parameters:
        cls = TestInteractiveRetry
    else:
        cls = MultinodeTestAction
    return cls


class MultinodeTestShell(LavaTest):
    """
    LavaTestShell Strategy object for Multinode
    """

    # higher priority than the plain TestShell
    priority = 2

    def __init__(self, parent, parameters):
        super().__init__(parent)
        cls = get_subaction_class(parameters)
        self.action = cls()
        self.action.job = self.job
        self.action.section = self.action_type
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if "role" in parameters:
            if MultinodeProtocol.name in parameters:
                if "target_group" in parameters[MultinodeProtocol.name]:
                    return True, "accepted"
                else:
                    return (
                        False,
                        '"target_group" was not in parameters for %s'
                        % MultinodeProtocol.name,
                    )
            else:
                return False, "%s was not in parameters" % MultinodeProtocol.name
        return False, '"role" not in parameters'

    @classmethod
    def needs_deployment_data(cls):
        """ Some, not all, deployments will want deployment_data """
        return True

    @classmethod
    def needs_overlay(cls):
        return True

    @classmethod
    def has_shell(cls):
        return True


class MultinodeTestAction(TestShellAction):

    name = "multinode-test"
    description = "Executing lava-test-runner"
    summary = "Multinode Lava Test Shell"
    timeout_exception = TestError

    def __init__(self):
        super().__init__()
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
        self.signal_director = self.SignalDirector(self.protocols[0])

    def check_patterns(self, event, test_connection, check_char):
        """
        Calls the parent check_patterns first, then checks for subclass pattern.
        """
        ret = super().check_patterns(event, test_connection, check_char)
        if event == "multinode":
            name, params = test_connection.match.groups()
            self.logger.debug("Received Multi_Node API <LAVA_%s>" % name)
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
        def __init__(self, protocol):
            super().__init__(protocol)
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
                    detail = str.split(message, "=")
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
