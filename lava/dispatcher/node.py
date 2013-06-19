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

from twisted.internet import reactor
from twisted.internet.protocol import Protocol, ReconnectingClientFactory
from socket import gethostname
import json
import logging
import os
import sys
from lava_dispatcher.config import get_config
from lava_dispatcher.job import LavaTestJob


class Node(Protocol):

    data = None
    client_name = ''
    request = None
    role = None
    group_size = 0
    message = None
    messageID = None
    complete = False
    finished = False
    json_jobdata = None
    oob_file = sys.stderr
    output_dir = None

    def __call__(self, args):
        try:
            self.nodeTransport(args)
        except KeyError:
            logging.debug("Bad call to NodeDispatcher:transport")

    def nodeTransport(self, message):
        if self.transport:
            logging.info("writing %s to the protocol transport" % message)
            self.transport.write(message)

    def setOutputData(self, json_jobdata, oobfile=sys.stderr, output_dir=None):
        self.json_jobdata = json_jobdata
        self.oob_file = oobfile
        self.output_dir = output_dir

    def setMessage(self, group_name, client_name, role, request_str=None):
        if group_name is None:
            raise ValueError('group name must not be empty')
        else:
            self.group_name = group_name
        if client_name is None:
            raise ValueError('client name must not be empty')
        else:
            self.client_name = client_name
        if role is None:
            raise ValueError('role must not be empty')
        else:
            self.role = role
        logging.info(request_str)
        if request_str:
            try:
                # the request must be in JSON
                request = json.loads(request_str)
            except Exception as e:
                logging.debug("Failed to parse %s: %s" % (request_str, e.message()))
                return
            if 'group_size' in request:
                self.group_size = request['group_size']
            if 'request' in request:
                self.request = request['request']
                if 'message' in request:
                    self.message = request['message']
                if 'messageID' in request:
                    self.messageID = request['messageID']
            else:
                self.request = request
        # do not try to send unicode, it must be str
        msg = {"group_name": self.group_name,
               "group_size": self.group_size,
               "client_name": self.client_name,
               # hostname here is the node hostname, not the server. (The server already knows the server hostname)
               "hostname": gethostname(),
               "role": self.role,
               "request": self.request,
               "messageID": self.messageID,
               "message": self.message
               }
        self.data = str(json.dumps(msg))
        if isinstance(self.data, unicode):
            raise ValueError("somehow we got unicode in the message: %s" % self.data)

    def getName(self):
        return self.client_name

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
        job.run(self)

    def dataReceived(self, data):
        if data == 'nack':
            logging.debug("Reply: %s" % data)
            self.transport.loseConnection()
        else:
            # deal with the message and pass down to the board
            logging.debug("Ack: %s" % self.data)
            if not self.complete:
                self.complete = True
                ack_msg = {"request": "complete"}
                self.run_tests(self.json_jobdata)
            if self.complete and not self.finished:
                self.finished = True
                ack_msg = {"request": "finished"}
            self.setMessage(self.group_name, self.client_name, self.role, json.dumps(ack_msg))
            self.transport.write(self.data)
            self.writeMessage()

    def completion(self):
        return self.complete

    def registerClient(self):
        logging.debug("Registering %s in group %s" % (self.client_name, self.group_name))
        self.transport.write(self.data)

    def writeMessage(self):
        """
         Writes out the message to the device filesystem.
         Message content could be group_data or a JSON message.
         TBD
        """
        self.transport.loseConnection()

    def getGroupData(self):
        logging.info("sending message: %s", self.data)
        self.transport.write(self.data)

    def connectionMade(self):
        self.registerClient()


class NodeClientFactory(ReconnectingClientFactory):

    client_name = None
    group_name = None
    request = None
    role = None
    client = Node()
    oob_file = sys.stderr
    output_dir = None
    json_jobdata = None

    def __init__(self, json_jobdata, oob_file=sys.stderr, output_dir=None):
        self.oob_file = oob_file
        self.output_dir = output_dir
        self.json_jobdata = json_jobdata

    def makeCall(self, group_name, client_name, role, request=None):
        self.group_name = group_name
        self.client_name = client_name
        self.request = request
        self.role = role

    def buildProtocol(self, addr):
        try:
            # FIXME: check if client is available to do this in __init__
            self.client.setOutputData(self.json_jobdata, self.oob_file, self.output_dir)
            self.client.setMessage(self.group_name, self.client_name, self.role, self.request)
        except Exception as e:
            logging.debug("Failed to build protocol: %s" % e.message)
            return None
        # FIXME: check how often this gets called
        self.resetDelay()
        return self.client

    def clientConnectionLost(self, connector, reason):
        """
        Handles how to respond when the GroupDispatcher closes the connection to allow
        the node to return to normal processing.
        :param connector: part of the twisted protocol stack
        :param reason: If 'complete', the setup part of the group->node communication is complete
        If 'finished' then all tests have also finished.
        """
        if not self.client.complete:
            ReconnectingClientFactory.clientConnectionLost(self, connector, reason)
        elif not self.client.finished:
            # FIXME: how does this affect the output data and the message?
            ReconnectingClientFactory.clientConnectionLost(self, connector, reason)
        else:
            logging.info("MulitNode communication complete for %s" % self.client_name)
            # only stop the reactor when all work is done, it cannot be restarted!
            reactor.stop()
            # control flow returns to commands.py:setup_multinode()

    def clientConnectionFailed(self, connector, reason):
        logging.debug("Connection failed. Reason: %s" % reason)
        ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)


class NodeDispatcher(object):

    group_name = ''
    group_size = 0
    group_port = 3079
    group_host = "localhost"
    target = ''
    role = ''

    def __init__(self, json_data, oob_file=sys.stderr, output_dir=None):
        """
        Parse the modified JSON to identify the group name,
        requested port for the group - node comms
        and get the designation for this node in the group.
        """
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
        group_msg = {"request": "group_data", "group_size": self.group_size}
        logging.debug("factory.makeCall(\"%s\", \"%s\", \"%s\", \"%s\")"
                      % (self.group_name, self.target, self.role, json.dumps(group_msg)))
        logging.debug("reactor.connectTCP(\"%s\", %d, factory)" % (self.group_host, self.group_port))
        try:
            factory = NodeClientFactory(json_data, oob_file, output_dir)
        except Exception as e:
            logging.warn("Unable to create the node client factory: %s." % e.message())
            return
        factory.makeCall(self.group_name, self.target, self.role, json.dumps(group_msg))
        reactor.connectTCP(self.group_host, self.group_port, factory)
        reactor.run()

    def send(self, msg):
        try:
            factory = NodeClientFactory()
        except Exception as e:
            logging.warn("Unable to create the node client factory: %s." % e.message())
            return
        factory.makeCall(self.group_name, self.target, self.role, json.dumps(msg))
        reactor.connectTCP(self.group_host, self.group_port, factory)
        reactor.run()

    def request_wait_all(self, messageID, role=None):
        """
        Asks the GroupDispatcher to send back a particular messageID
        and blocks until that messageID is available for all nodes in
        this group or all nodes with the specified role in this group.
        """
        if role:
            self.send({"request": "lava_wait", "role": role})
        else:
            self.send({"request": "lava_wait_all"})

    def request_wait(self, messageID):
        """
        Asks the GroupDispatcher to send back a particular messageID
        and blocks until that messageID is available for this node
        """
        # use self.target as the node ID
        wait_msg = {"request": "lava_wait",
                    "messageID": messageID,
                    "nodeID": self.target}
        self.send(wait_msg)

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
        self.send(send_msg)

    # FIXME: lava_sync needs to support a message.
    def request_sync(self):
        """
        Creates and send a message requesting lava_sync
        """
        sync_msg = {"request": "lava_sync"}
        self.send(sync_msg)


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
