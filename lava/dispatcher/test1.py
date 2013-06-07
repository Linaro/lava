#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  test.py
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

from twisted.internet import reactor
from twisted.internet.protocol import Protocol, ReconnectingClientFactory


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
        # do this with pickle..
        self.data = "{ \"group_name\": \"%s\", \"client_name\": \"%s\", \"request\": \"%s\" }" \
               % (self.group_name, self.client_name, self.request)

    def getName(self):
        return self.client_name

    def dataReceived(self, data):
        if data == 'nack':
            print("Reply: %s" % data)
            self.transport.loseConnection()
        else:
            print("Ack: %s" % self.data)
            self.setMessage(self.group_name, self.client_name, 'complete')
            self.complete = True
            self.transport.write(self.data)
            self.writeGroupData

    def completion(self):
        return self.complete

    def registerClient(self):
        print("Registering %s in group %s" % (self.client_name, self.group_name))
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
            print "Failed to build protocol: %s" % e.message
            return None
        self.resetDelay()
        return self.client

    def clientConnectionLost(self, connector, reason):
        if not self.client.complete:
            ReconnectingClientFactory.clientConnectionLost(self, connector, reason)
        else:
            print 'Communication complete for %s' % self.client_name
            reactor.stop()

    def clientConnectionFailed(self, connector, reason):
        print 'Connection failed. Reason:', reason
        ReconnectingClientFactory.clientConnectionFailed(self, connector,reason)

factory = NodeClientFactory()
factory.makeCall('test', 'client01', "group_data")
reactor.connectTCP('localhost', 3079, factory)
reactor.run()
