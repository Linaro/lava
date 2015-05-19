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


import copy
import json
import logging
import os
import socket
import time
from lava_dispatcher.pipeline.connection import Protocol
from lava_dispatcher.pipeline.action import (
    Timeout,
    JobError,
    InfrastructureError,
    TestError
)
from lava_dispatcher.pipeline.utils.constants import LAVA_MULTINODE_SYSTEM_TIMEOUT


class MultinodeProtocol(Protocol):
    """
    Multinode API protocol - one instance per Multinode job
    """
    name = "lava-multinode"

    # FIXME: use errors and valid where old code just logged complaints

    def __init__(self, parameters):
        super(MultinodeProtocol, self).__init__(parameters)
        self.blocks = 4 * 1024
        # how long between polls (in seconds)
        self.system_timeout = Timeout('system', LAVA_MULTINODE_SYSTEM_TIMEOUT)
        self.settings = None
        self.sock = None
        self.base_message = None
        self.logger = logging.getLogger('dispatcher')
        self.delayed_start = False
        params = parameters['protocols'][self.name]
        if 'request' in params and 'lava-start' == params['request'] and 'expect_role' in params:
            if params['expect_role'] != params['role']:
                self.delayed_start = True
                self.system_timeout.duration = Timeout.parse(params['timeout'])
            else:
                self.errors = "expect_role must not match the role declaring lava_start"
                self.logger.warning(self.errors)

    @classmethod
    def accepts(cls, parameters):
        if 'protocols' not in parameters:
            return False
        if 'lava-multinode' not in parameters['protocols']:
            return False
        if 'target_group' in parameters['protocols'][cls.name]:
            return True
        return False

    def read_settings(self, filename):
        """
        NodeDispatchers need to use the same port and blocksize as the Coordinator,
        so read the same conffile.
        The protocol header is hard-coded into the server & here.
        """
        settings = {
            "port": 3079,
            "blocksize": 4 * 1024,
            "poll_delay": 1,
            "coordinator_hostname": "localhost"
        }
        json_default = {}
        with open(filename) as stream:
            jobdata = stream.read()
            try:
                json_default = json.loads(jobdata)
            except ValueError as exc:
                raise InfrastructureError("Invalid JSON settings for %s: %s" % (self.name, exc))
        if "port" in json_default:
            settings['port'] = json_default['port']
        if "blocksize" in json_default:
            settings['blocksize'] = json_default["blocksize"]
        if "poll_delay" in json_default:
            settings['poll_delay'] = json_default['poll_delay']
        if "coordinator_hostname" in json_default:
            settings['coordinator_hostname'] = json_default['coordinator_hostname']
        return settings

    def _connect(self, delay):
        """
        create socket and connect
        """
        # FIXME: needs to comply with system timeout
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.connect((self.settings['coordinator_hostname'], self.settings['port']))
            return True
        except socket.error as exc:
            self.logger.exception(
                "socket error on connect: %d %s %s" % (
                    exc.errno, self.settings['coordinator_hostname'], self.settings['port']))
            time.sleep(delay)
            self.sock.close()
            return False

    def _send_message(self, message):
        msg_len = len(message)
        try:
            # send the length as 32bit hexadecimal
            ret_bytes = self.sock.send("%08X" % msg_len)
            if ret_bytes == 0:
                self.logger.debug("zero bytes sent for length - connection closed?")
                return False
            ret_bytes = self.sock.send(message)
            if ret_bytes == 0:
                self.logger.debug("zero bytes sent for message - connection closed?")
                return False
        except socket.error as exc:
            self.logger.exception("socket error '%d' on send" % exc.message)
            self.sock.close()
            return False
        return True

    def _recv_message(self):
        try:
            header = self.sock.recv(8)  # 32bit limit as a hexadecimal
            if not header or header == '':
                self.logger.debug("empty header received?")
                return json.dumps({"response": "wait"})
            msg_count = int(header, 16)
            recv_count = 0
            response = ''
            while recv_count < msg_count:
                response += self.sock.recv(self.blocks)
                recv_count += self.blocks
        except socket.error as exc:
            self.logger.exception("socket error '%d' on response" % exc.errno)
            self.sock.close()
            return json.dumps({"response": "wait"})
        return response

    def poll(self, message, timeout=None):
        """
        Blocking, synchronous polling of the Coordinator on the configured port.
        Single send operations greater than 0xFFFF are rejected to prevent truncation.
        :param msg_str: The message to send to the Coordinator, as a JSON string.
        :return: a JSON string of the response to the poll
        """
        if not timeout:
            timeout = self.poll_timeout.duration
        msg_len = len(message)
        if msg_len > 0xFFFE:
            raise JobError("Message was too long to send!")
        c_iter = 0
        response = None
        delay = self.settings['poll_delay']
        self.logger.debug("Connecting to LAVA Coordinator on %s:%s timeout=%d seconds." % (
            self.settings['coordinator_hostname'], self.settings['port'], timeout))
        while True:
            c_iter += self.settings['poll_delay']
            if self._connect(delay):
                delay = self.settings['poll_delay']
            else:
                delay += 2
                continue
            if not c_iter % int(10 * self.settings['poll_delay']):
                self.logger.debug("sending message: %s waited %s of %s seconds" % (
                    json.loads(message)['request'], c_iter, int(timeout)))
            # blocking synchronous call
            if not self._send_message(message):
                continue
            self.sock.shutdown(socket.SHUT_WR)
            response = self._recv_message()
            self.sock.close()
            try:
                json_data = json.loads(response)
            except ValueError:
                self.logger.debug("response starting '%s' was not JSON" % response[:42])
                self.finalise_protocol()
                break
            if json_data['response'] != 'wait':
                break
            else:
                time.sleep(delay)
            # apply the default timeout to each poll operation.
            if c_iter > timeout:
                self.finalise_protocol()
                raise JobError("protocol %s timed out" % self.name)
        return response

    def set_up(self):
        """
        Called from the job at the start of the run step.
        """
        # FIXME: add the coordinator.conf data to the job data to avoid installing lava-coordinator on dispatchers.
        filename = "/etc/lava-coordinator/lava-coordinator.conf"
        if not os.path.exists(filename):
            raise InfrastructureError("Missing coordinator configuration")
        else:
            self.settings = self.read_settings(filename)
        self.base_message = {
            "port": self.settings['port'],
            "blocksize": self.settings['blocksize'],
            "poll_delay": self.settings["poll_delay"],
            "host": self.settings['coordinator_hostname'],
            # hostname here is the node hostname, not the server.
            "hostname": socket.gethostname(),
            'client_name': self.parameters['target'],
            "group_name": self.parameters['protocols'][self.name]['target_group'],
            "role": self.parameters['protocols'][self.name]['role'],
        }
        self.initialise_group()
        if self.delayed_start:
            # delayed start needs to pull the sync timeout from the job parameters.
            self.logger.info("%s protocol initialised - start is delayed by up to %s seconds" % (
                self.name, self.system_timeout.duration))
            expect_role = self.parameters['protocols'][self.name]['expect_role']
            self.logger.debug("Delaying start for %s seconds, lava_wait_all for role %s" % (
                self.system_timeout.duration, expect_role))
            # send using the system timeout
            sync_msg = {
                "request": "lava_wait_all",
                "waitrole": expect_role,
                "messageID": 'lava_start'}
            self._send(sync_msg, True)
            self.logger.debug("sent %s" % sync_msg)
        else:
            self.logger.debug("%s protocol initialised" % self.name)

    def debug_setup(self):
        self.settings = {
            'blocksize': 4096,
            'port': 3179,  # debug port
            'coordinator_hostname': u'localhost',
            'poll_delay': 3
        }

        self.base_message = {
            "port": self.settings['port'],
            "blocksize": self.settings['blocksize'],
            "poll_delay": self.settings["poll_delay"],
            "host": self.settings['coordinator_hostname'],
            # hostname here is the node hostname, not the server.
            "hostname": socket.gethostname(),
            'client_name': self.parameters['target'],
            "group_name": self.parameters['protocols'][self.name]['target_group'],
            "role": self.parameters['protocols'][self.name]['role'],
        }
        if self.delayed_start:
            self.logger.debug("Debug: delayed start activated, waiting for %s" %
                              self.parameters['protocols'][self.name]['expect_role'])
        self.logger.debug("%s protocol initialised in debug mode" % self.name)

    def initialise_group(self):
        """
        Sends the first message to initialize the group data
        separated so that unit tests can choose whether to use debug_setup with or without it.
        """
        init_msg = {
            "request": "group_data",
            "group_size": self.parameters['protocols'][self.name]['group_size']
        }
        self.logger.debug("Initialising group %s" % self.parameters['protocols'][self.name]['target_group'])
        self._send(init_msg, True)

    def finalise_protocol(self):
        fin_msg = {
            "request": "clear_group",
            "group_size": self.parameters['protocols'][self.name]['group_size']
        }
        self._send(fin_msg, True)
        self.logger.debug("%s protocol finalised." % self.name)

    def _check_data(self, data):
        try:
            json_data = json.loads(data)
        except (ValueError, TypeError) as exc:
            raise JobError("Invalid data for %s protocol: %s %s" % (self.name, data, exc))
        if type(json_data) != dict:
            raise JobError("Invalid data type %s for protocol %s" % (data, self.name))
        if not json_data:
            raise JobError("No data to be sent over protocol %s" % self.name)
        if 'request' not in json_data:
            raise JobError("Bad API call over protocol - missing request")
        if json_data["request"] == "aggregate":
            raise JobError("Pipeline submission has not been implemented.")
        if "poll_delay" in json_data:
            self.settings['poll_delay'] = int(json_data["poll_delay"])
        if 'timeout' in json_data:
            self.poll_timeout = Timeout(self.name, json_data['timeout'])
        if 'messageID' not in json_data:
            raise JobError("Missing messageID")
        # handle conversion of api calls to internal functions
        json_data['request'] = json_data['request'].replace('-', '_')

        return json_data

    def _api_select(self, data):
        """ Determines which API call has been requested, makes the call, blocks and returns the reply.
        :param json_data: Python object of the API call
        :return: Python object containing the reply dict.
        """
        if not data:
            raise TestError("Protocol called without any data")
        json_data = self._check_data(data)
        reply_str = ''
        message_id = json_data['messageID']

        if json_data['request'] == "lava_sync":
            self.logger.debug("requesting lava_sync '%s'" % message_id)
            reply_str = self.request_sync(message_id)

        elif json_data['request'] == 'lava_wait':
            self.logger.debug("requesting lava_wait '%s'" % message_id)
            reply_str = self.request_wait(message_id)

        elif json_data['request'] == 'lava_wait_all':
            if 'role' in json_data and json_data['role'] is not None:
                reply_str = self.request_wait_all(message_id, json_data['role'])
                self.logger.debug("requesting lava_wait_all '%s' '%s'" % (message_id, json_data['role']))
            else:
                self.logger.debug("requesting lava_wait_all '%s'" % message_id)
                reply_str = self.request_wait_all(message_id)

        elif json_data['request'] == "lava_send":
            self.logger.debug("requesting lava_send %s" % message_id)
            if 'message' in json_data and json_data['message'] is not None:
                send_msg = json_data['message']
                if type(send_msg) is not dict:
                    send_msg = {json_data['message']: None}
                self.logger.debug("message: %s", send_msg)
                if 'yaml_line' in send_msg:
                    del send_msg['yaml_line']
                self.logger.debug("requesting lava_send %s with args %s" % (message_id, send_msg))
                reply_str = self.request_send(message_id, send_msg)
            else:
                self.logger.debug("requesting lava_send %s without args" % message_id)
                reply_str = self.request_send(message_id)

        if reply_str == '':
            raise TestError("Unsupported api call: %s" % json_data['request'])
        reply = json.loads(str(reply_str))
        if 'message' in reply:
            return reply['message']
        else:
            return reply['response']

    def __call__(self, args):
        try:
            return self._api_select(json.dumps(args))
        except (ValueError, TypeError) as exc:
            raise JobError("Invalid call to %s %s" % (self.name, exc))

    def collate(self, reply, params):
        """
        Retrieve values from reply to the call for this action
        possibly multiple key:value pairs.
        Arguments: reply - self.get_common_data(protocol.name, self.name)
                   params - dict containing the message to match to the reply
        params will not be modified, the return value is a *tuple* where the first value
        is the identifier to be used by other actions wanting this data (typically the API call or messageID)
        and the second value is the collated data from the call to the protocol.
        """
        retval = {}
        if 'message' in params and 'message' in reply:
            replaceables = [key for key, value in params['message'].items()
                            if key != 'yaml_line' and value.startswith('$')]
            for item in replaceables:
                data = [val for val in reply['message'].items() if self.parameters['target'] in val][0][1]
                retval.setdefault(params['messageID'], {item: data[item]})
        ret_key = params['messageID']
        ret_value = retval[ret_key]
        return ret_key, ret_value

    def _send(self, msg, system=False):
        """ Internal call to perform the API call via the Poller.
        :param msg: The call-specific message to be wrapped in the base_msg primitive.
        :return: Python object of the reply dict.
        """
        new_msg = copy.deepcopy(self.base_message)
        new_msg.update(msg)
        if system:
            return self.poll(json.dumps(new_msg), timeout=self.system_timeout.duration)
        self.logger.debug("final message: %s" % json.dumps(new_msg))
        return self.poll(json.dumps(new_msg))

    def request_wait_all(self, message_id, role=None):
        """
        Asks the Coordinator to send back a particular messageID
        and blocks until that messageID is available for all nodes in
        this group or all nodes with the specified role in this group.
        """
        # FIXME: if this node has not called request_send for the
        # messageID used for a wait_all, the node should log a warning
        # of a broken test definition. (requires a change in the coordinator)
        if role:
            return self._send({"request": "lava_wait_all",
                               "messageID": message_id,
                               "waitrole": role})
        else:
            return self._send({"request": "lava_wait_all",
                               "messageID": message_id})

    def request_wait(self, message_id):
        """
        Asks the Coordinator to send back a particular messageID
        and blocks until that messageID is available for this node
        """
        # use self.target as the node ID
        wait_msg = {"request": "lava_wait",
                    "messageID": message_id,
                    "nodeID": self.parameters['target']}
        return self._send(wait_msg)

    def request_send(self, message_id, message=None):
        """
        Sends a message to the group via the Coordinator. The
        message is guaranteed to be available to all members of the
        group. The message is only picked up when a client in the group
        calls lava_wait or lava_wait_all.
        The message needs to be formatted JSON, not a simple string.
        { "messageID": "string", "message": { "key": "value"} }
        The message can consist of just the messageID:
        { "messageID": "string" }
        """
        self.logger.debug("request_send %s %s" % (message_id, message))
        if not message:
            message = {}
        send_msg = {"request": "lava_send",
                    "messageID": message_id,
                    "message": message}
        self.logger.debug("Sending %s" % send_msg)
        return self._send(send_msg)

    def request_sync(self, msg):
        """
        Creates and send a message requesting lava_sync
        """
        sync_msg = {"request": "lava_sync", "messageID": msg}
        return self._send(sync_msg)

    def request_lava_start(self, message):
        """
        Sends a message to the group via the Coordinator. All jobs with the matching role
        will receive the message and can then start the job.
        """
        send_msg = {"request": "lava_send",
                    "messageID": 'lava_start',
                    "message": message}
        return self._send(send_msg)
