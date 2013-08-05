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
            self.log.info("seen a header")
            self.header = False
            assert(int(data, 16) < 0xFFFE)
            self.log.info("Header length: %d" % int(data, 16))
        else:
            try:
                json_data = json.loads(data)
            except ValueError:
                assert False
            if not self.test_name:
                assert(json_data['response'] == "nack")
            if self.test_name == "bad":
                assert(json_data['response'] == "nack")
            self.header = True

    def close(self):
        self.log.info("closing testsocket")

    def prepare(self, name):
        self.log.info("preparing")
        self.test_name = name


class TestCoordinator(LavaCoordinator):

    running = True
    json_data = None
    group_name = str(uuid.uuid4())
    client_name = None
    conn = None
    log = None

    def __init__(self):
        super(LavaCoordinator, self).__init__()
        self.conn = TestSocket()
        self.log = logging.getLogger("testCase")
        self.log.info("Testing coordinator")
        self.json_data = {"request": "testing"}
        self.client_name = "testpoller"
        self.log.info("Starting test with %s %d %d %s" %
                      (json.dumps(self.json_data), self.rpc_delay,
                       self.blocksize, self.host))
        self._prepare(None)

    # sets up TestSocket for the correct assertions
    def _prepare(self, test_name):
        self.conn.prepare(test_name)

    def run(self):
        self._badRequest()
        return self._updateData({"client_name": self.client_name,
                                "group_name": self.group_name})


class TestPoller(unittest.TestCase):

    coord = None

    def setUp(self):
        self.coord = TestCoordinator()

    def test_01_poll(self):
        self.coord.dataReceived({})
    
    def test_02_receive(self):
        self.coord._prepare(None)
    
    def test_02_run(self):
        ret = self.coord.run()
        self.assertTrue(ret is None)


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
