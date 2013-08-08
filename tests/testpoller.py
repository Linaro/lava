#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  testpoller.py
#
#  Copyright 2013 Neil Williams <codehelp@debian.org>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#

import unittest
import logging
import sys
import uuid
import json
from lava.coordinator import LavaCoordinator


class TestSignals(object):

    message_str = ''

    def formatString(self, reply):
        if type(reply) is dict:
            for target, messages in reply.items():
                for key, value in messages.items():
                    self.message_str += " %s:%s=%s" % (target, key, value)
        return self.message_str

    def checkMessage(self, reply):
        if reply is not None:
            self.log = logging.getLogger("testCase")
            self.log.info("\t<LAVA_TEST_COMPLETE%s>" % self.formatString(reply))


class TestSocket(object):

    response = None
    header = True
    log = None
    message = None
    passes = 0
    signalHandler = None

    def __init__(self):
        self.log = logging.getLogger("testCase")
        self.signalHandler = TestSignals()

    def send(self, data):
        if self.header:
            self.header = False
            assert(int(data, 16) < 0xFFFE)
            self.log.info("\tCoordinator header: %d bytes" % int(data, 16))
        else:
            try:
                json_data = json.loads(data)
            except ValueError:
                assert False
            if not self.response:
                assert(json_data['response'] == "nack")
                self.header = True
                return
            assert 'response' in json_data
            self.log.info("\tCoordinator response: '%s'" % json_data['response'])
            assert(json_data['response'] == self.response)
            self.passes += 1
            if self.message:
                # we are expecting a message back.
                assert 'message' in json_data
                self.log.info("\tCoordinator received a message: '%s'" % (json.dumps(json_data['message'])))
                assert(json_data['message'] == self.message)
                self.passes += 1
            else:
                # actual calls will discriminate between dict and string replies
                # according to the call prototype itself
                if "message" in json_data:
                    if type(json_data['message']) is dict:
                        self.log.info("\tCould have expected a message: '%s'" % json.dumps(json_data['message']))
                    else:
                        self.log.info("\t<LAVA_TEST_REPLY %s>" % json_data['message'])
                self.passes += 1
            self.header = True

    def close(self):
        self.log.info("\tCoordinator closing.")

    def clearPasses(self):
        self.passes = 0

    def logPasses(self):
        if self.passes == 1:
            self.log.info("\tCoordinator: %d socket test passed" % self.passes)
        else:
            self.log.info("\tCoordinator: %d socket tests passed" % self.passes)

    def prepare(self, name):
        self.response = name
        if self.response:
            self.log.info("\tCoordinator: expecting a response: '%s'" % self.response)

    def validate(self, message):
        self.message = message
        if self.message:
            self.log.info("\tCoordinator: expecting a message: '%s'" % json.dumps(self.message))
        self.signalHandler.checkMessage(self.message)


class TestCoordinator(LavaCoordinator):

    running = True
    json_data = None
    group_name = None
    group_size = 0
    client_name = None
    conn = None
    log = None

    def __init__(self):
        super(LavaCoordinator, self).__init__()
        self.group_name = str(uuid.uuid4())
        self.conn = TestSocket()
        self.log = logging.getLogger("testCase")
        self.log.info("")
        self.json_data = {"request": "testing"}
        self.client_name = "testpoller"
        self.log.info("\tStarting test with %s %d %d %s" %
                      (json.dumps(self.json_data), self.rpc_delay,
                       self.blocksize, self.host))
        self.expectResponse(None)

    def newGroup(self, size):
        self.group_name = str(uuid.uuid4())
        self.group_size = size
        self.log = logging.getLogger("testCase")
        self.log.info("\tGroup name %s" % self.group_name)

    # sets up TestSocket for the correct assertions
    def expectResponse(self, test_name):
        self.conn.prepare(test_name)

    def expectMessage(self, message):
        self.conn.validate(message)

    def addClient(self, client_name):
        self.conn.response = "ack"
        self.client_name = client_name
        self.log = logging.getLogger("testCase")
        ret = self._updateData({"client_name": client_name,
                                "group_size": self.group_size,
                                "role": "tester",
                                "hostname": "localhost",
                                "group_name": self.group_name})
        self.log.info("\tAdded client_name '%s'. group size now: %d" %
                      (client_name, len(self.group['clients'])))
        self.log.info("\tCurrent client_name: '%s'" % self.client_name)
        return ret

    def addClientRole(self, client_name, role):
        self.conn.response = "ack"
        self.client_name = client_name
        self.log = logging.getLogger("testCase")
        ret = self._updateData({"client_name": client_name,
                                "group_size": self.group_size,
                                "role": role,
                                "hostname": "localhost",
                                "group_name": self.group_name})
        self.log.info("\tAdded client_name '%s' with role '%s'. group size now: %d" %
                      (client_name, role, len(self.group['clients'])))
        self.log.info("\tCurrent client_name: '%s'" % self.client_name)
        return ret


class TestPoller(unittest.TestCase):

    coord = None
    role = None

    def setUp(self):
        self.coord = TestCoordinator()

    def _wrapMessage(self, message, role):
        base_msg = {
            "timeout": 90,
            "client_name": self.coord.client_name,
            "group_name": self.coord.group_name,
            "role": role,
        }
        base_msg.update(message)
        # uncomment to get verbose output
#        self.log = logging.getLogger("testCase")
#        self.log.info("\tmessage content: '%s'" % json.dumps(base_msg))
        return base_msg

    def _switch_client(self, name):
        self.coord.client_name = name

    def _cleanup(self):
        self.log = logging.getLogger("testCase")
        self.log.info("\tClearing group %s after test" % self.coord.group_name)
        old_name = self.coord.group_name
        self.coord.expectResponse("ack")
        self.coord.expectMessage(None)
        while self.coord.group_size > 0:
            self.coord._clearGroupData({"group_name": old_name})
            self.coord.group_size -= 1
        # clear the group name and data
        self.assertTrue(self.coord.group['group'] != old_name)
        self.assertTrue(self.coord.group['group'] == '')
        self.log.info("\tGroup %s cleared correctly." % old_name)
        self.coord.conn.clearPasses()

    def test_01_poll(self):
        """ Check that an empty message gives an empty response
        """
        self.coord.dataReceived({})

    def test_02_receive(self):
        """ Explicitly expect an empty response with an empty message
        """
        self.coord.expectResponse(None)
        self.coord.dataReceived({})

    def test_03_missing_client_name(self):
        """ Send a malformed message with no client_name, expect a warning
        """
        self.log = logging.getLogger("testCase")
        self.log.info("\tExpect warning of a missing client name in request")
        ret = self.coord._updateData({"group_name": self.coord.group_name})
        self.assertTrue(ret is None)

    def test_04_missing_group_size(self):
        """ Send a malformed message with no group_size, expect a warning.
        """
        self.log = logging.getLogger("testCase")
        self.log.info("\tExpect warning of new group without specifying the size of the group")
        ret = self.coord._updateData({
            "client_name": self.coord.client_name,
            "group_name": self.coord.group_name
        })
        self.assertTrue(ret is None)

    def test_05_start_group_incomplete(self):
        """ Create a group but fail to populate it with enough devices and cleanup
        """
        self.coord.group_name = str(uuid.uuid4())
        self.coord.group_size = 2
        self.coord.conn.response = "ack"
        self.coord.client_name = "incomplete"
        self.log = logging.getLogger("testCase")
        ret = self.coord._updateData(
            {"client_name": self.coord.client_name,
             "group_size": self.coord.group_size,
             "role": "tester",
             "hostname": "localhost",
             "group_name": self.coord.group_name})
        self.log.info("\tAdded client_name '%s'. group size now: %d" %
                      (self.coord.client_name, len(self.coord.group['clients'])))
        self.log.info("\tCurrent client_name: '%s'" % self.coord.client_name)
        self.coord.group_size = 1
        self.assertTrue(ret == "incomplete")
        self._cleanup()

    def test_06_start_group_complete(self):
        """ Create a group with enough devices and check for no errors.
        """
        self.coord.newGroup(2)
        ret = self.coord.addClient("completing")
        self.assertTrue(ret == "completing")
        ret = self.coord.addClient("completed")
        self.assertTrue(ret == "completed")
        self._cleanup()

    def test_07_lava_send_check(self):
        """ Create a deliberate typo of an API call and check for a warning.
        """
        self.coord.newGroup(2)
        self.coord.addClient("node_one")
        self.coord.addClient("node_two")
        self.log = logging.getLogger("testCase")
        self.log.info("\tExpect warning of an unrecognised request due to deliberate typo.")
        self.coord.expectResponse("nack")
        send_msg = {"request": "lava-send",
                    "messageID": "sending_test",
                    "message": None}
        self.coord.dataReceived(self._wrapMessage(send_msg, "tester"))
        self.coord.expectResponse("ack")
        send_msg = {"request": "lava_send",
                    "messageID": "sending_test",
                    "message": None}
        self.coord.dataReceived(self._wrapMessage(send_msg, "tester"))
        self._cleanup()

    def test_08_lava_send_keypair(self):
        """ lava-send key=value - expect an ack
        """
        self.coord.newGroup(2)
        self.coord.addClient("node one")
        self.coord.addClient("node two")
        send_msg = {"request": "lava_send",
                    "messageID": "keyvalue_test",
                    "message": {
                        "key": "value"
                    }}
        self.log = logging.getLogger("testCase")
        self.log.info("\tINF: simply send a message and check for ack")
        self.coord.expectResponse("ack")
        self.coord.dataReceived(self._wrapMessage(send_msg, "tester"))
        self._cleanup()

    def test_09_lava_wait_check(self):
        """ lava-wait check without key value pairs
        """
        self.coord.newGroup(2)
        self.coord.addClient("node_one")
        self.coord.addClient("node_two")
        self.coord.expectResponse("ack")
        send_msg = {"request": "lava_send",
                    "messageID": "sending_test",
                    "message": None}
        self.coord.dataReceived(self._wrapMessage(send_msg, "tester"))
        wait_msg = {"request": "lava_wait",
                    "messageID": "missing message",
                    "message": None}
        self.log = logging.getLogger("testCase")
        self.log.info("\tINF: wait for a message not already sent.")
        self.coord.expectResponse("wait")
        self.coord.dataReceived(self._wrapMessage(wait_msg, "tester"))
        self.coord.expectResponse("ack")
        self.log.info("\tINF: wait for a message which has already been sent.")
        self.coord.expectResponse("ack")
        self.coord.dataReceived(self._wrapMessage(send_msg, "tester"))
        self.coord.expectResponse("ack")
        self._cleanup()

    def test_10_lava_wait_keypair(self):
        """ lava-wait check with key=value
        """
        self.coord.newGroup(2)
        self.coord.addClient("node_one")
        self.coord.addClient("node_two")
        self.coord.expectResponse("ack")
        message = {"key": "value"}
        send_msg = {"request": "lava_send",
                    "messageID": "keyvalue_test",
                    "message": message}
        self.coord.dataReceived(self._wrapMessage(send_msg, "tester"))
        self.coord.expectResponse("ack")
        message = {self.coord.client_name: {"key": "value"}}
        self.coord.expectMessage(message)
        wait_msg = {"request": "lava_wait",
                    "messageID": "keyvalue_test",
                    "message": None}
        self.coord.dataReceived(self._wrapMessage(wait_msg, "tester"))
        self.coord.expectMessage(None)
        self._cleanup()

    def test_11_lava_wait_all(self):
        """ lava-wait-all check
        """
        self.coord.newGroup(2)
        self.coord.addClient("node_one")
        self.coord.addClient("node_two")
        self.coord.expectResponse("ack")
        send_msg = {"request": "lava_send",
                    "messageID": "waitall_test",
                    "message": None}
        self.coord.dataReceived(self._wrapMessage(send_msg, "tester"))
        self.log = logging.getLogger("testCase")
        self.log.info("\tINF: send from node_two first, expect wait")
        wait_msg = {"request": "lava_wait_all",
                    "messageID": "waitall_test",
                    "message": None}
        self.coord.expectResponse("wait")
        self.coord.dataReceived(self._wrapMessage(wait_msg, "tester"))
        self.log.info("\tINF: test node_one waiting before sending a message itself")
        # FIXME: this may need to become a "nack" with the node outputting a warning
        self._switch_client("node_one")
        self.coord.expectResponse("wait")
        self.coord.dataReceived(self._wrapMessage(wait_msg, "tester"))
        self.log.info("\tINF: now allow node_one to send the right message")
        self.coord.expectResponse("ack")
        self.coord.dataReceived(self._wrapMessage(send_msg, "tester"))
        self.log.info("\tINF: test node_one after sending a message")
        self._switch_client("node_one")
        self.coord.expectResponse("ack")
        message = {"node_one": {}, "node_two": {}}
        self.coord.expectMessage(message)
        self.coord.dataReceived(self._wrapMessage(wait_msg, "tester"))
        self._cleanup()

    def test_12_lava_sync(self):
        """ lava-sync check
        """
        self.coord.newGroup(2)
        self.coord.addClient("node_one")
        self.coord.addClient("node_two")
        self.coord.expectResponse("wait")
        self.log = logging.getLogger("testCase")
        self.log.info("\tINF: %s requests a sync" % self.coord.client_name)
        sync_msg = {"request": "lava_sync",
                    "messageID": "waitall_test",
                    "message": None}
        self.coord.dataReceived(self._wrapMessage(sync_msg, "tester"))
        self._switch_client("node_one")
        self.log.info("\tINF: %s requests a sync" % self.coord.client_name)
        self.coord.expectResponse("wait")
        self.coord.dataReceived(self._wrapMessage(sync_msg, "tester"))
        self.coord.expectResponse("ack")
        self.coord.dataReceived(self._wrapMessage(sync_msg, "tester"))
        self._switch_client("node_two")
        self.log.info("\tINF: %s requests a sync" % self.coord.client_name)
        self.coord.expectResponse("ack")
        self.coord.dataReceived(self._wrapMessage(sync_msg, "tester"))
        self._cleanup()

    def test_13_lava_wait_all_role(self):
        """ lava-wait-all check with role limitation.
        """
        self.coord.newGroup(3)
        self.coord.addClientRole("client_one", "client")
        self.coord.addClientRole("client_two", "client")
        self.coord.addClientRole("server", "server")
        self.log = logging.getLogger("testCase")
        self._switch_client("client_two")
        self.log.info("\tINF: one client waiting before lava_send on any client")
        self.coord.expectResponse("nack")
        wait_msg = {"request": "lava_wait_all",
                    "messageID": "wait-all-role",
                    "message": None}
        self.coord.dataReceived(self._wrapMessage(wait_msg, "client"))
        self.log.info("\tINF: Send a message to this group")
        send_msg = {"request": "lava_send",
                    "messageID": "wait-all-role",
                    "message": None}
        self.coord.expectResponse("ack")
        self.coord.dataReceived(self._wrapMessage(send_msg, "client"))
        self.log.info("\tINF:one client waiting before lava_send on the other client")
        self.coord.expectResponse("wait")
        wait_msg = {"request": "lava_wait_all",
                    "messageID": "wait-all-role",
                    "message": None}
        self.coord.dataReceived(self._wrapMessage(wait_msg, "client"))
        self._switch_client("server")
        # FIXME: this may need to become a "nack" with the node outputting a warning
        self.log.info("\tINF:server waiting before lava_send on the other client")
        self.coord.expectResponse("wait")
        wait_msg = {"request": "lava_wait_all",
                    "messageID": "wait-all-role",
                    "waitrole": "client",
                    "message": None}
        self.coord.dataReceived(self._wrapMessage(wait_msg, "server"))
        self._switch_client("client_one")
        self.log.info("\tINF:Send a message to this group")
        send_msg = {"request": "lava_send",
                    "messageID": "wait-all-role",
                    "message": None}
        self.coord.expectResponse("ack")
        self.coord.dataReceived(self._wrapMessage(send_msg, "client"))
        wait_msg = {"request": "lava_wait_all",
                    "messageID": "wait-all-role",
                    "waitrole": "client",
                    "message": None}
        self.coord.expectResponse("ack")
        message = {"client_two": {}, "client_one": {}}
        self.coord.expectMessage(message)
        self.coord.dataReceived(self._wrapMessage(wait_msg, "client"))
        self._cleanup()

    def test_14_lava_wait_all_keypair(self):
        """ lava-wait-all with key value pairs
        """
        self.coord.newGroup(3)
        self.coord.addClientRole("client_one", "client")
        self.coord.addClientRole("client_two", "client")
        self.coord.addClientRole("server", "server")
        self.log = logging.getLogger("testCase")
        self._switch_client("client_two")
        self.coord.expectResponse("ack")
        message = {"key": "value"}
        send_msg = {"request": "lava_send",
                    "messageID": "keyvalue_test",
                    "message": message}
        self.coord.dataReceived(self._wrapMessage(send_msg, "client"))
        self.coord.expectResponse("wait")
        wait_msg = {"request": "lava_wait_all",
                    "messageID": "keyvalue_test",
                    "message": None}
        self.coord.dataReceived(self._wrapMessage(wait_msg, "client"))
        self.coord.dataReceived(self._wrapMessage(wait_msg, "client"))
        self.coord.dataReceived(self._wrapMessage(wait_msg, "client"))
        self.log.info("\tINF: wait_all - so other clients need to send before we get the message")
        self._switch_client("client_one")
        self.coord.expectResponse("ack")
        self.coord.dataReceived(self._wrapMessage(send_msg, "client"))
        self.coord.expectResponse("wait")
        self.coord.dataReceived(self._wrapMessage(wait_msg, "client"))
        self.coord.dataReceived(self._wrapMessage(wait_msg, "client"))
        self.coord.dataReceived(self._wrapMessage(wait_msg, "client"))
        self.log.info("\tINF: this is a wait_all without a role - so server must send too.")
        self._switch_client("server")
        self.coord.expectResponse("ack")
        self.coord.dataReceived(self._wrapMessage(send_msg, "server"))
        message = {"client_two": {"key": "value"},
                   "client_one": {"key": "value"},
                   "server": {"key": "value"}}
        self.coord.expectResponse("ack")
        self.coord.expectMessage(message)
        self.coord.dataReceived(self._wrapMessage(wait_msg, "server"))
        self._cleanup()

    def test_15_lava_wait_all_role_keypair(self):
        """ lava-wait-all with key value pairs and role limitation.
        """
        self.coord.newGroup(3)
        self.coord.addClientRole("client_one", "client")
        self.coord.addClientRole("client_two", "client")
        self.coord.addClientRole("server", "server")
        self.log = logging.getLogger("testCase")
        self._switch_client("client_two")
        self.coord.expectResponse("ack")
        message = {"key": "value"}
        send_msg = {"request": "lava_send",
                    "messageID": "keyvalue_test",
                    "message": message}
        self.coord.dataReceived(self._wrapMessage(send_msg, "client"))
        self.coord.expectResponse("wait")
        wait_msg = {"request": "lava_wait_all",
                    "messageID": "keyvalue_test",
                    "waitrole": "client",
                    "message": None}
        self.coord.dataReceived(self._wrapMessage(wait_msg, "client"))
        self.coord.dataReceived(self._wrapMessage(wait_msg, "client"))
        self.coord.dataReceived(self._wrapMessage(wait_msg, "client"))
        self.log.info("\tINF: wait_all - so other clients need to send before we get the message")
        self._switch_client("client_one")
        self.coord.expectResponse("ack")
        self.coord.dataReceived(self._wrapMessage(send_msg, "client"))
        message = {"client_two": {"key": "value"},
                   "client_one": {"key": "value"}}
        self.coord.expectResponse("ack")
        self.coord.expectMessage(message)
        self.coord.dataReceived(self._wrapMessage(wait_msg, "client"))
        self.log.info("\tINF: this is a wait_all with a role - so server will be ignored.")
        self._switch_client("server")
        self.coord.expectMessage(None)
        self.coord.expectResponse("ack")
        self.coord.dataReceived(self._wrapMessage(send_msg, "server"))
        self.log.info("\tINF: call to wait by the server was ignored.")
        self.coord.expectResponse("ack")
        self.log.info("\tINF: checking that the messageID is persistent.")
        message = {"client_two": {"key": "value"},
                   "client_one": {"key": "value"},
                   "server": {"key": "value"}}
        self.coord.expectMessage(message)
        self.coord.dataReceived(self._wrapMessage(wait_msg, "client"))
        self._cleanup()

    def test_16_lava_network(self):
        """ Simulate calls to lava-network using real data from multinode.validation.linaro.org
        at the node & coordinator level.
        """
        msg02 = {"message": {
            "hostname-full": "imx53-02.localdomain", "hostname": "imx53-02",
            "netmask": "Mask:255.255.0.0", "dns_1": "192.168.1.32",
            "default-gateway": "192.168.1.1", "ipv6": "addr:",
            "ipv4": "addr:192.168.106.189"},
            "request": "lava_send", "messageID": "network_info"}
        msg04 = {"message": {
            "hostname-full": "imx53-04.localdomain", "hostname": "imx53-04",
            "netmask": "Mask:255.255.0.0", "dns_1": "192.168.1.32",
            "default-gateway": "192.168.1.1", "ipv6": "addr:",
            "ipv4": "addr:192.168.106.180"},
            "request": "lava_send", "messageID": "network_info"}
        reply = {"imx53-02": {"hostname-full": "imx53-02.localdomain",
                              "hostname": "imx53-02", "netmask": "Mask:255.255.0.0",
                              "dns_1": "192.168.1.32", "default-gateway": "192.168.1.1",
                              "ipv6": "addr:", "ipv4": "addr:192.168.106.189"},
                 "imx53-04": {"hostname-full": "imx53-04.localdomain",
                              "hostname": "imx53-04", "netmask": "Mask:255.255.0.0",
                              "dns_1": "192.168.1.32", "default-gateway": "192.168.1.1",
                              "ipv6": "addr:", "ipv4": "addr:192.168.106.180"}}
        self.coord.newGroup(2)
        self.coord.addClientRole("imx53-02", "network")
        self.coord.addClientRole("imx53-04", "network")
        self.log = logging.getLogger("testCase")
        self.log = logging.getLogger("testCase")
        self.log.info("\tINF: Start by sending data for imx53-02 (broadcast)")
        self._switch_client("imx53-02")
        self.coord.expectResponse("ack")
        self.coord.dataReceived(self._wrapMessage(msg02, "network"))
        self.log.info("\tINF: collect should wait until the other client sends.")
        wait_msg = {"request": "lava_wait_all",
                    "messageID": "network_info",
                    "message": None}
        self.coord.expectResponse("wait")
        self.coord.dataReceived(self._wrapMessage(wait_msg, "network"))
        self.coord.expectResponse("wait")
        self.coord.dataReceived(self._wrapMessage(wait_msg, "network"))
        self.coord.expectResponse("wait")
        self.coord.dataReceived(self._wrapMessage(wait_msg, "network"))
        self.log.info("\tINF: Send data for imx53-04")
        self._switch_client("imx53-04")
        self.coord.expectResponse("ack")
        self.coord.dataReceived(self._wrapMessage(msg04, "network"))
        wait_msg = {"request": "lava_wait_all",
                    "messageID": "network_info",
                    "message": None}
        self.coord.expectResponse("ack")
        self.coord.expectMessage(reply)
        self.coord.dataReceived(self._wrapMessage(wait_msg, "network"))
        self._cleanup()


def main():
    FORMAT = '%(msg)s'
    logging.basicConfig(format=FORMAT)
    logging.basicConfig(stream=sys.stderr)
    logging.getLogger("testCase").setLevel(logging.DEBUG)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPoller)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    if not res.wasSuccessful():
        sys.exit(1)
    return 0

if __name__ == '__main__':
    main()
