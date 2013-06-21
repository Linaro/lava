#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  node.py
#
#  Copyright 2013 Linaro Limited
#  Author Neil Williams <neil.williams@linaro.org>
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

import socket
from socket import gethostname
import json
import logging
import os
import copy
import sys
import time
from lava_dispatcher.config import get_config
from lava_dispatcher.job import LavaTestJob


class Poller(object):
    """
    Blocking, synchronous socket poller which repeatedly tries to connect
    to the GroupDispatcher, get a very fast response and then implement the
    wait.
    If the node needs to wait, it will get a {"response": "wait"}
    If the node should stop polling and send data back to the board, it will
    get a {"response": "ack", "message": "blah blah"}
    """

    port = 3079
    json_data = None
    polling = False
    delay = 1
    blocks = 1024

    def __init__(self, data_str):
        print "Poller init passed json_data", data_str
        try:
            self.json_data = json.loads(data_str)
        except ValueError:
            print "bad JSON"
            exit(1)
        if 'port' in self.json_data:
            self.port = self.json_data['port']
        if 'blocksize' in self.json_data:
            self.blocks = self.json_data['blocksize']
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print "have socket"

    def poll(self, msg):
        print "polling %s" % json.dumps(self.json_data)
        self.polling = True
        while self.polling:
            try:
                print "host:%s port:%s" % (self.json_data['host'], self.json_data['port'])
                ret = self.s.connect_ex(('localhost', self.json_data['port']))
                print "connect returned", ret
                if ret:
                    print "not connected: %d" % ret
                    self.s.close()
                    continue
                self.delay = 1
                print "connected", ret
            except socket.error:
                time.sleep(self.delay)
                self.delay *= 2
            print "msg %s" % msg
            # blocking synchronous call
            try:
                self.s.send(msg)
            except socket.error as e:
                print "socket error", e.message
#                self.s.shutdown(socket.SHUT_RDWR)
                self.s.close()
                continue
            try:
                self.response = self.s.recv(self.blocks)
            except socket.error as e:
                print "socket error", e.message
#                self.s.shutdown(socket.SHUT_RDWR)
                self.s.close()
                continue
            # free up the GroupDispatcher for more connections and messages
#            self.s.shutdown(socket.SHUT_RDWR)
            self.s.close()
            try:
                json_data = json.loads(self.response)
            except ValueError:
                logging.error("response was not JSON %s" % self.response)
                break
            if json_data['response'] != 'wait':
                logging.info(json_data['response'])
                self.polling = False
                break
        return self.response


class NodeDispatcher(object):

    group_name = ''
    group_size = 0
    group_port = 3079
    group_host = "localhost"
    target = ''
    role = ''
    factory = None
    poller = None
    oob_file = sys.stderr
    output_dir = None
    base_msg = None
    json_data = None

    def __init__(self, json_data, oob_file=sys.stderr, output_dir=None):
        """
        Parse the modified JSON to identify the group name,
        requested port for the group - node comms
        and get the designation for this node in the group.
        """
        self.json_data = json_data
        # FIXME: do this with a schema once the API settles
        if 'target_group' not in json_data:
            raise ValueError("Invalid JSON to work with the MultiNode GroupDispatcher: no target_group.")
        self.group_name = json_data['target_group']
        if 'group_size' not in json_data:
            raise ValueError("Invalid JSON to work with the GroupDispatcher: no group_size")
        self.group_size = json_data["group_size"]
        if 'target' not in json_data:
            raise ValueError("Invalid JSON for a child node: no target designation.")
        self.target = json_data['target']
        if 'port' in json_data:
            self.group_port = json_data['port']
        if 'role' in json_data:
            self.role = json_data['role']
        # hostname of the server for the connection.
        if 'hostname' in json_data:
            self.group_host = json_data['hostname']
        self.base_msg = {"port": self.group_port,
                         "host": self.group_host,
                         "client_name": json_data['target'],
                         "group_name": json_data['target_group'],
                         # hostname here is the node hostname, not the server.
                         "hostname": gethostname(),
                         "role": self.role,
                         }
        self.poller = Poller(json.dumps(self.base_msg))
        self.oob_file = oob_file
        self.output_dir = output_dir

    def run(self):
        init_msg = {"request": "group_data", "group_size": self.group_size}
        init_msg.update(self.base_msg)
        print "NodeDispatcher: init_msg", json.dumps(init_msg)
        self.poller.poll(json.dumps(init_msg))
        self.run_tests(self.json_data)

    def __call__(self, args):
        try:
            logging.info("transport handler for NodeDispatcher %s" % args)
            self._select(json.loads(args))
        except KeyError:
            logging.warn("Unable to use callable send in NodeDispatcher")

    def _select(self, json_data):
        if not json_data:
            logging.debug("Empty args")
            return
        if 'request' not in json_data:
            logging.debug("Bad call")
            return
        if json_data['request'] == "lava_sync":
            logging.info("requesting sync")
            # FIXME: pointless redirection unles request_sync does more work eventually.
            self.request_sync(json_data['messageID'])

    def send(self, msg):
        new_msg = copy.deepcopy(self.base_msg)
        new_msg.update(msg)
        logging.info("sending Message %s" % json.dumps(new_msg))
        return self.poller.poll(new_msg)

    def request_wait_all(self, messageID, role=None):
        """
        Asks the GroupDispatcher to send back a particular messageID
        and blocks until that messageID is available for all nodes in
        this group or all nodes with the specified role in this group.
        """
        if role:
            return self.send({"request": "lava_wait", "role": role})
        else:
            return self.send({"request": "lava_wait_all"})

    def request_wait(self, messageID):
        """
        Asks the GroupDispatcher to send back a particular messageID
        and blocks until that messageID is available for this node
        """
        # use self.target as the node ID
        wait_msg = {"request": "lava_wait",
                    "messageID": messageID,
                    "nodeID": self.target}
        return self.send(wait_msg)

    def request_send(self, client_name, message):
        """
        Sends a message to the group via the GroupDispatcher. The 
        message is guaranteed to be available to all members of the
        group. The message is only picked up when a client in the group
        calls lava_wait or lava_wait_all.
        The message needs to be formatted JSON, not a simple string.
        { "messageID": "string", "message": { "key": "value"} }
        The message can consist of just the messageID:
        { "messageID": "string" }
        """
        if 'messageID' not in message:
            logging.debug("No messageID specified - not sending")
            return
        send_msg = {"request": "lava_send",
                    "destination": client_name,
                    "messageID": message['messageID'],
                    "message": message['message']}
        return self.send(send_msg)

    # FIXME: lava_sync needs to support a message.
    def request_sync(self, msg):
        """
        Creates and send a message requesting lava_sync
        """
        sync_msg = {"request": "lava_sync", "messageID": msg}
        self.send(sync_msg)

    def run_tests(self, json_jobdata):
        config = get_config()
        if 'logging_level' in json_jobdata:
            logging.root.setLevel(json_jobdata["logging_level"])
        else:
            logging.root.setLevel(config.logging_level)
        # FIXME: how to get args.target to the node?
#        if self.args.target is None:
        if 'target' not in json_jobdata:
            logging.error("The job file does not specify a target device. You must specify one using the --target option.")
            exit(1)
#        else:
#            json_jobdata['target'] = self.args.target
        jobdata = json.dumps(json_jobdata)
        if self.output_dir and not os.path.isdir(self.output_dir):
            os.makedirs(self.output_dir)
        job = LavaTestJob(jobdata, self.oob_file, config, self.output_dir)
        # pass this NodeDispatcher down so that the lava_test_shell can __call__ nodeTransport to write a message
#        job.run(self.dispatcher)
        job.run(self)
        logging.info("job.run has returned")

    def writeMessage(self):
        """
         Writes out the message to the device filesystem.
         Message content could be group_data or a JSON message.
         TBD
        """
        pass


def main():
    """
    Only used for local debug,
    """
    with open("/home/neil/code/lava/bundles/node.json") as stream:
        jobdata = stream.read()
        json_jobdata = json.loads(jobdata)
    print json_jobdata
    node = NodeDispatcher(json_jobdata)
    return 0

if __name__ == '__main__':
    main()
