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

    test_name = None
    header = True
    log = None

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
            if not self.test_name:
                assert(json_data['response'] == "nack")
            if self.test_name == "bad":
                assert(json_data['response'] == "nack")
            if self.test_name == "good":
                assert(json_data['response'] == "ack")
            self.header = True

    def close(self):
        self.log.info("\tclosing testsocket")

    def prepare(self, name):
        self.test_name = name
        if self.test_name:
            self.log.info("\tpreparing '%s' test" % self.test_name)


class TestCoordinator(LavaCoordinator):

    running = True
    json_data = None
    group_name = None
    client_name = None
    conn = None
    log = None

    def __init__(self):
        super(LavaCoordinator, self).__init__()
        self._new_group()
        self.conn = TestSocket()
        self.log = logging.getLogger("testCase")
        self.log.info("")
        self.json_data = {"request": "testing"}
        self.client_name = "testpoller"
        self.log.info("\tStarting test with %s %d %d %s" %
                      (json.dumps(self.json_data), self.rpc_delay,
                       self.blocksize, self.host))
        self._prepare(None)

    def _new_group(self):
        self.group_name = str(uuid.uuid4())

    # sets up TestSocket for the correct assertions
    def _prepare(self, test_name):
        self.conn.prepare(test_name)

    def run(self, client_name, group_size):
        self.conn.test_name = "good"
        self.client_name = client_name
        self.log = logging.getLogger("testCase")
        self.log.info("\trun with %s %d" % (client_name, group_size))
        return self._updateData({"client_name": client_name,
                                "group_size": group_size,
                                "role": "tester",
                                "hostname": "localhost",
                                "group_name": self.group_name})


class TestPoller(unittest.TestCase):

    coord = None

    def _cleanup(self, group_size=1):
        self.log = logging.getLogger("testCase")
        self.log.info("\tClearing group %s after test" % self.coord.group_name)
        old_name = self.coord.group_name
        while group_size > 0:
            self.coord._clearGroupData({"group_name": old_name})
            group_size -= 1
        # clear the group name and data
        self.assertTrue(self.coord.group['group'] != old_name)
        self.assertTrue(self.coord.group['group'] == '')
        self.log.info("\tgroup %s cleared correctly." % old_name)
        
    def setUp(self):
        self.coord = TestCoordinator()

    def test_01_poll(self):
        self.coord.dataReceived({})
    
    def test_02_receive(self):
        self.coord._prepare(None)

    def test_03_missing_client_name(self):
        self.log = logging.getLogger("testCase")
        self.log.info("\tgroup name %s" % self.coord.group_name)
        self.log.info("\tExpect warning of a missing client name in request")
        ret = self.coord._updateData({"group_name": self.coord.group_name})
        self.assertTrue(ret is None)
    
    def test_04_missing_group_size(self):
        self.log = logging.getLogger("testCase")
        self.log.info("\tgroup name %s" % self.coord.group_name)
        self.log.info("\tExpect warning of new group without specifying the size of the group")
        ret = self.coord._updateData({
            "client_name": self.coord.client_name,
            "group_name": self.coord.group_name
        })
        self.assertTrue(ret is None)

    def test_05_start_group_incomplete(self):
        self.log = logging.getLogger("testCase")
        self.log.info("\tgroup name %s" % self.coord.group_name)
        ret = self.coord.run("incomplete", 2)
        self.assertTrue(ret == "incomplete")
        self._cleanup()

    def test_06_start_group_complete(self):
        self.coord._new_group()
        self.log = logging.getLogger("testCase")
        self.log.info("\tgroup name %s" % self.coord.group_name)
        ret = self.coord.run("completing", 2)
        self.assertTrue(ret == "completing")
        ret = self.coord.run("completed", 2)
        self.assertTrue(ret == "completed")
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
