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


class Node(Protocol):

    data = None
    client_name = ''
    request = None
    message = None
    messageID = None
    complete = False

    def setMessage(self, group_name, client_name, request_str=None):
        if group_name is None:
            raise ValueError('group name must not be empty')
        else:
            self.group_name = group_name
        if client_name is None:
            raise ValueError('client name must not be empty')
        else:
            self.client_name = client_name
        logging.info(request_str)
        if request_str:
            try:
                # the request must be in JSON
                request = json.loads(request_str)
            except Exception as e:
                logging.debug("Failed to parse %s: %s" % (request_str, e.message()))
                return
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
               "client_name": self.client_name,
               # hostname here is the node hostname, not the server. (The server already knows the server hostname)
               "hostname": gethostname(),
               "request": self.request,
               "messageID": self.messageID,
               "message": self.message
               }
        self.data = str(json.dumps(msg))
        if isinstance(self.data, unicode):
            raise ValueError("somehow we got unicode in the message: %s" % self.data)

    def getName(self):
        return self.client_name

    def dataReceived(self, data):
        if data == 'nack':
            logging.debug("Reply: %s" % data)
            self.transport.loseConnection()
        else:
            logging.debug("Ack: %s" % self.data)
            complete = {"request": "complete"}
            self.setMessage(self.group_name, self.client_name, json.dumps(complete))
            self.complete = True
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
    client = Node()

    def makeCall(self, group_name, client_name, request=None):
        self.group_name = group_name
        self.client_name = client_name
        self.request = request

    def buildProtocol(self, addr):
        try:
            self.client.setMessage(self.group_name, self.client_name, self.request)
        except Exception as e:
            logging.debug("Failed to build protocol: %s" % e.message)
            return None
        self.resetDelay()
        return self.client

    def clientConnectionLost(self, connector, reason):
        if not self.client.complete:
            ReconnectingClientFactory.clientConnectionLost(self, connector, reason)
        else:
            logging.info("MulitNode communication complete for %s" % self.client_name)
            reactor.stop()

    def clientConnectionFailed(self, connector, reason):
        logging.debug("Connection failed. Reason: %s" % reason)
        ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)


class NodeDispatcher(object):

    group_name = ''
    group_port = 3079
    group_host = "localhost"
    target = ''
    
    def __init__(self, json_data):
        """
        Parse the modified JSON to identify the group name,
        requested port for the group - node comms
        and get the designation for this node in the group.
        """
        # FIXME: do this with a schema once the API settles
        if 'target_group' not in json_data:
            raise ValueError("Invalid JSON for a MultiNode GroupDispatcher: no target_group.")
        self.group_name = json_data['target_group']
        if 'target' not in json_data:
            raise ValueError("Invalid JSON for a child node: no target designation.")
        self.target = json_data['target']
        if 'port' in json_data:
            self.group_port = json_data['port']
        # hostname of the server for the connection.
        if 'hostname' in json_data:
            self.group_host = json_data['hostname']
        group_msg = {"request": "group_data"}
        logging.debug("factory.makeCall(\"%s\", \"%s\", \"%s\")"
                      % (self.group_name, self.target, json.dumps(group_msg)))
        logging.debug("reactor.connectTCP(\"%s\", %d, factory)" % (self.group_host, self.group_port))
        try:
            factory = NodeClientFactory()
        except Exception as e:
            logging.warn("Unable to create the node client factory: %s." % e.message())
            return
        factory.makeCall(self.group_name, self.target, json.dumps(group_msg))
        reactor.connectTCP(self.group_host, self.group_port, factory)
        reactor.run()

    def request_wait_all(self, messageID, role=None):
        """
        Asks the GroupDispatcher to send back a particular messageID
        and blocks until that messageID is available for all nodes in
        this group or all nodes with the specified role in this group.
        """
        pass

    def request_wait(self, messageID):
        """
        Asks the GroupDispatcher to send back a particular messageID
        and blocks until that messageID is available for this node
        """
        # use self.target as the node ID
        pass

    def request_send(self, client_name, message):
        """
        Sends a message to a particular client via the GroupDispatcher
        The message is only picked up via lava_wait or lava_wait_all
        message needs to be formatted JSON, not a simple string.
        { "messageID": "string", "message": { "key": "value"} }
        The message can consist of just the messageID:
        { "messageID": "string" }
        """
        msg = 'lava_send'
        
        try:
            factory = NodeClientFactory()
        except Exception as e:
            logging.warn("Unable to create the node client factory: %s." % e.message())
            return
        factory.makeCall(self.group_name, self.target, msg)
        reactor.connectTCP(self.group_host, self.group_port, factory)
        reactor.run()

    def request_sync(self):
        """
        Creates and send a message requesting lava_sync
        """
        msg = 'lava_sync'
        try:
            factory = NodeClientFactory()
        except Exception as e:
            logging.warn("Unable to create the node client factory: %s." % e.message())
            return
        factory.makeCall(self.group_name, self.target, msg)
        reactor.connectTCP(self.group_host, self.group_port, factory)
        reactor.run()


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
