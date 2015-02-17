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
from lava_dispatcher.pipeline.actions.test.shell import TestShellAction
from lava_dispatcher.pipeline.action import TestError, JobError, Timeout
from lava_dispatcher.pipeline.actions.test import LavaTest
from lava_dispatcher.pipeline.protocols.multinode import MultinodeProtocol


class MultinodeTestShell(LavaTest):
    """
    LavaTestShell Strategy object for Multinode
    """
    # higher priority than the plain TestShell
    priority = 2

    def __init__(self, parent, parameters):
        super(MultinodeTestShell, self).__init__(parent)
        self.action = MultinodeTestAction()
        self.action.job = self.job
        self.action.section = self.action_type
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):  # pylint: disable=unused-argument
        if 'role' in parameters:
            if MultinodeProtocol.name in parameters:
                if 'target_group' in parameters[MultinodeProtocol.name]:
                    return True
        return False


class MultinodeTestAction(TestShellAction):

    def __init__(self):
        super(MultinodeTestAction, self).__init__()
        self.name = "multinode-test"
        self.description = "Executing lava-test-runner"
        self.summary = "Multinode Lava Test Shell"

    def validate(self):
        super(MultinodeTestAction, self).validate()
        # MultinodeProtocol is required, others can be optional
        if MultinodeProtocol.name not in [protocol.name for protocol in self.job.protocols]:
            self.errors = "Invalid job - missing protocol"
        if MultinodeProtocol.name not in [protocol.name for protocol in self.protocols]:
            self.errors = "Missing protocol"
        if not self.valid:
            self.errors = "Invalid base class TestAction"
            return
        self.patterns.update({
            'multinode': r'<LAVA_MULTI_NODE> <LAVA_(\S+) ([^>]+)>',
        })
        self.signal_director.setup(self.parameters)

    def populate(self, parameters):
        """
        Select the appropriate protocol supported by this action from the list available from the job
        """
        self.protocols = [protocol for protocol in self.job.protocols if protocol.name == MultinodeProtocol.name]
        self.signal_director = self.SignalDirector(self.protocols[0])

    def check_patterns(self, event, test_connection):
        """
        Calls the parent check_patterns first, then checks for subclass pattern.
        """
        ret = super(MultinodeTestAction, self).check_patterns(event, test_connection)
        if event == 'multinode':
            name, params = test_connection.match.groups()
            self.logger.debug("Received Multi_Node API <LAVA_%s>" % name)
            params = params.split()
            try:
                ret = self.signal_director.signal(name, params)
            except JobError as exc:
                self.logger.exception("Job error in %s signal: %s %s" % (event, exc, name))
                return False
            return ret
        return ret

    class SignalDirector(TestShellAction.SignalDirector):

        def __init__(self, protocol):
            super(MultinodeTestAction.SignalDirector, self).__init__(protocol)
            self.base_message = {}

        def setup(self, parameters):
            """
            Retrieve the poll_timeout from the protocol parameters which are set after init.
            """
            if MultinodeProtocol.name not in parameters:
                return
            if 'timeout' in parameters[MultinodeProtocol.name]:
                self.base_message = {
                    'timeout': Timeout.parse(parameters[MultinodeProtocol.name]['timeout'])
                }

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
            self.connection.sendline("<LAVA_SYNC_COMPLETE%s>" % message_str)

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
            self.connection.sendline("<LAVA_WAIT_COMPLETE%s>" % message_str)

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
            self.connection.sendline("<LAVA_WAIT_ALL_COMPLETE%s>" % message_str)
