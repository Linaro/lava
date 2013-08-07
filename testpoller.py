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
from coordinator import LavaCoordinator


class TestSocket(object):

    response = None
    header = True
    log = None
    message = None
    passes = 0

    def __init__(self):
        self.log = logging.getLogger("testCase")

    def send(self, data):
        if self.header:
            self.log.info("\tseen a header")
            self.header = False
            assert(int(data, 16) < 0xFFFE)
            self.log.info("\tHeader length: %d" % int(data, 16))
        else:
            try:
                json_data = json.loads(data)
            except ValueError:
                assert False
            if not self.response:
                assert(json_data['response'] == "nack")
                self.header = True
                return
            self.log.info("\tresponse=%s" % json_data['response'])
            assert(json_data['response'] == self.response)
            self.passes += 1
            if self.message:
                self.log.info("\treceived a message: '%s'" % json.dumps(json_data['message']))
                assert(json_data['message'] == self.message)
                self.passes += 1
            self.header = True

    def close(self):
        self.log.info("\tclosing testsocket")

    def clearPasses(self):
        self.passes = 0

    def logPasses(self):
        if self.passes == 1:
            self.log.info("\t%d socket test passed" % self.passes)
        else:
            self.log.info("\t%d socket tests passed" % self.passes)

    def prepare(self, name):
        self.response = name
        if self.response:
            self.log.info("\texpecting a response: '%s'" % self.response)

    def validate(self, message):
        self.message = message
        if self.message:
            self.log.info("\texpecting a message: '%s'" % json.dumps(self.message))


class TestCoordinator(LavaCoordinator):

    running = True
    json_data = None
    group_name = None
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

    def newGroup(self):
        self.group_name = str(uuid.uuid4())
        self.log = logging.getLogger("testCase")
        self.log.info("\tgroup name %s" % self.group_name)

    # sets up TestSocket for the correct assertions
    def expectResponse(self, test_name):
        self.conn.prepare(test_name)

    def expectMessage(self, message):
        self.conn.validate(message)

    def addClient(self, client_name, group_size):
        self.conn.response = "ack"
        self.client_name = client_name
        self.log = logging.getLogger("testCase")
        ret = self._updateData({"client_name": client_name,
                                "group_size": group_size,
                                "role": "tester",
                                "hostname": "localhost",
                                "group_name": self.group_name})
        self.log.info("\tadded client_name '%s'. group size now: %d" %
                      (client_name, len(self.group['clients'])))
        self.log.info("\tcurrent client_name: '%s'" % self.client_name)
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
#        self.log = logging.getLogger("testCase")
#        self.log.info("\tmessage content: '%s'" % json.dumps(base_msg))
        return base_msg

    def _switch_client(self, name):
        self.coord.client_name = name

    def _cleanup(self, group_size=1):
        self.log = logging.getLogger("testCase")
        self.log.info("\tClearing group %s after test" % self.coord.group_name)
        old_name = self.coord.group_name
        self.coord.expectResponse("ack")
        while group_size > 0:
            self.coord._clearGroupData({"group_name": old_name})
            group_size -= 1
        # clear the group name and data
        self.assertTrue(self.coord.group['group'] != old_name)
        self.assertTrue(self.coord.group['group'] == '')
        self.log.info("\tgroup %s cleared correctly." % old_name)
        self.coord.conn.logPasses()
        self.coord.conn.clearPasses()

    def test_01_poll(self):
        self.coord.dataReceived({})

    def test_02_receive(self):
        self.coord.expectResponse(None)
        self.coord.dataReceived({})

    def test_03_missing_client_name(self):
        self.log = logging.getLogger("testCase")
        self.log.info("\tExpect warning of a missing client name in request")
        ret = self.coord._updateData({"group_name": self.coord.group_name})
        self.assertTrue(ret is None)

    def test_04_missing_group_size(self):
        self.log = logging.getLogger("testCase")
        self.log.info("\tExpect warning of new group without specifying the size of the group")
        ret = self.coord._updateData({
            "client_name": self.coord.client_name,
            "group_name": self.coord.group_name
        })
        self.assertTrue(ret is None)

    def test_05_start_group_incomplete(self):
        ret = self.coord.addClient("incomplete", 2)
        self.assertTrue(ret == "incomplete")
        self._cleanup()

    def test_06_start_group_complete(self):
        self.coord.newGroup()
        ret = self.coord.addClient("completing", 2)
        self.assertTrue(ret == "completing")
        ret = self.coord.addClient("completed", 2)
        self.assertTrue(ret == "completed")
        self._cleanup(2)

    def test_07_lava_send_check(self):
        self.coord.newGroup()
        self.coord.addClient("node_one", 2)
        self.coord.addClient("node_two", 2)
        self.log = logging.getLogger("testCase")
        self.log.info("\tExpect warning of an unrecognised request due to deliberate typo.")
        self.coord.expectResponse("nack")
        # badly formatted call
        send_msg = {"request": "lava-send",
                    "messageID": "sending_test",
                    "message": None}
        self.coord.dataReceived(self._wrapMessage(send_msg, "tester"))
        self.coord.expectResponse("ack")
        send_msg = {"request": "lava_send",
                    "messageID": "sending_test",
                    "message": None}
        self.coord.dataReceived(self._wrapMessage(send_msg, "tester"))
        self._cleanup(2)

    def test_08_lava_send_keypair(self):
        self.coord.newGroup()
        self.coord.addClient("node one", 2)
        self.coord.addClient("node two", 2)
        send_msg = {"request": "lava_send",
                    "messageID": "keyvalue_test",
                    "message": {
                        "key": "value"
                    }}
        self.coord.dataReceived(self._wrapMessage(send_msg, "tester"))
        self._cleanup(2)

    def test_09_lava_wait_check(self):
        self.coord.newGroup()
        self.coord.addClient("node_one", 2)
        self.coord.addClient("node_two", 2)
        self.coord.expectResponse("ack")
        send_msg = {"request": "lava_send",
                    "messageID": "sending_test",
                    "message": None}
        self.coord.dataReceived(self._wrapMessage(send_msg, "tester"))
        wait_msg = {"request": "lava_wait",
                    "messageID": "missing message",
                    "message": None}
        self.log = logging.getLogger("testCase")
        self.log.info("\twait for a message not already sent.")
        self.coord.expectResponse("wait")
        self.coord.dataReceived(self._wrapMessage(wait_msg, "tester"))
        self.coord.expectResponse("ack")
        self.log.info("\twait for a message which has already been sent.")
        self.coord.expectResponse("ack")
        self.coord.dataReceived(self._wrapMessage(send_msg, "tester"))
        self.coord.expectResponse("ack")
        self._cleanup(2)

    def test_10_lava_wait_keypair(self):
        self.coord.newGroup()
        self.coord.addClient("node_one", 2)
        self.coord.addClient("node_two", 2)
        self.coord.expectResponse("ack")
        message = {"key": "value"}
        send_msg = {"request": "lava_send",
                    "messageID": "keyvalue_test",
                    "message": message}
        self.coord.dataReceived(self._wrapMessage(send_msg, "tester"))
        self.coord.expectResponse("ack")
        self.coord.expectMessage({self.coord.client_name: message})
        wait_msg = {"request": "lava_wait",
                    "messageID": "keyvalue_test",
                    "message": None}
        self.coord.dataReceived(self._wrapMessage(wait_msg, "tester"))
        self.coord.expectMessage(None)
        self._cleanup(2)

    def test_11_lava_wait_all(self):
        self.coord.newGroup()
        self.coord.addClient("node_one", 2)
        self.coord.addClient("node_two", 2)
        self.coord.expectResponse("ack")
        send_msg = {"request": "lava_send",
                    "messageID": "waitall_test",
                    "message": None}
        self.coord.dataReceived(self._wrapMessage(send_msg, "tester"))
        self.log = logging.getLogger("testCase")
        self.log.info("\tsend from node_two first, expect wait")
        wait_msg = {"request": "lava_wait_all",
                    "messageID": "waitall_test",
                    "message": None}
        self.coord.expectResponse("wait")
        self.coord.dataReceived(self._wrapMessage(wait_msg, "tester"))
        self.log.info("\ttest node_one waiting before sending a message itself")
        # FIXME: this may need to become a "nack" with the node outputting a warning
        self._switch_client("node_one")
        self.coord.expectResponse("wait")
        self.coord.dataReceived(self._wrapMessage(wait_msg, "tester"))
        self.log.info("\tnow allow node_one to send the right message")
        self.coord.expectResponse("ack")
        self.coord.dataReceived(self._wrapMessage(send_msg, "tester"))
        self.log.info("\ttest node_one after sending a message")
        self._switch_client("node_one")
        self.coord.expectResponse("ack")
        self.coord.dataReceived(self._wrapMessage(wait_msg, "tester"))
        self._cleanup(2)
        
    def test_12_lava_sync(self):
        self.coord.newGroup()
        self.coord.addClient("node_one", 2)
        self.coord.addClient("node_two", 2)
        self.coord.expectResponse("wait")
        self.log = logging.getLogger("testCase")
        self.log.info("\t%s requests a sync" % self.coord.client_name)
        sync_msg = {"request": "lava_sync",
                    "messageID": "waitall_test",
                    "message": None}
        self.coord.dataReceived(self._wrapMessage(sync_msg, "tester"))
        self._switch_client("node_one")
        self.log.info("\t%s requests a sync" % self.coord.client_name)
        self.coord.expectResponse("wait")
        self.coord.dataReceived(self._wrapMessage(sync_msg, "tester"))
        self.coord.expectResponse("ack")
        self.coord.dataReceived(self._wrapMessage(sync_msg, "tester"))
        self._switch_client("node_two")
        self.log.info("\t%s requests a sync" % self.coord.client_name)
        self.coord.expectResponse("ack")
        self.coord.dataReceived(self._wrapMessage(sync_msg, "tester"))
        self._cleanup(2)
        

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
