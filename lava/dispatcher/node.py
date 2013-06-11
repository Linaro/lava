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
import json
import logging


class Node(Protocol):

    data = None
    client_name = ''
    request = None
    complete = False

    def setMessage(self, group_name, client_name, request=None):
        if group_name is None:
            raise ValueError('group name must not be empty')
        else:
            self.group_name = group_name
        if client_name is None:
            raise ValueError('client name must not be empty')
        else:
            self.client_name = client_name
        self.request = request
        # do this with pickle.. but do not try to send unicode, it must be str
        self.data = str("{ \"group_name\": \"%s\", \"client_name\": \"%s\", \"request\": \"%s\" }" \
               % (self.group_name, self.client_name, self.request))
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
            self.setMessage(self.group_name, self.client_name, 'complete')
            self.complete = True
            self.transport.write(self.data)
            self.writeGroupData

    def completion(self):
        return self.complete

    def registerClient(self):
        logging.debug("Registering %s in group %s" % (self.client_name, self.group_name))
        self.transport.write(self.data)

    def writeGroupData(self):
        """
         Writes out the complete GroupData to the device filesystem."
         TBD
         """
        self.transport.loseConnection()

    def getGroupData(self):
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
        ReconnectingClientFactory.clientConnectionFailed(self, connector,reason)


class NodeDispatcher(object):

    def __init__(self, json_data):
        """
        Parse the modified JSON to identify the group name,
        requested port for the group - node comms
        and get the designation for this node in the group.
        """
        # FIXME: do this with a schema once the API settles
        if 'target_group' not in json_data:
            raise ValueError("Invalid JSON for a MultiNode GroupDispatcher: no target_group.")
        group_name = json_data['target_group']
        group_port = 3079
        group_host = "localhost"
        if 'target' not in json_data:
            raise ValueError("Invalid JSON for a child node: no target designation.")
        target = json_data['target']
        if 'port' in json_data:
            group_port = json_data['port']
        if 'hostname' in json_data:
            group_host = json_data['hostname']
        logging.debug("factory.makeCall(\"%s\", \"%s\", \"group_data\")" % (group_name,target))
        logging.debug("reactor.connectTCP(\"%s\", %d, factory)" % (group_host, group_port))
        factory = NodeClientFactory()
        factory.makeCall(group_name, target, "group_data")
        reactor.connectTCP(group_host, group_port, factory)
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
