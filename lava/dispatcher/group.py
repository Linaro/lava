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

import logging
from twisted.internet import reactor
from twisted.internet.protocol import Factory, Protocol
from twisted.internet.endpoints import TCP4ServerEndpoint
import json


class MultiNode(Protocol):
    """
    Protocol for communication between the parent dispatcher
    and child dispatchers.
    """
    all_groups = {}
    # FIXME: consider folding this into a data class?
    # All data handling for each connection happens on this local reference into the
    # all_groups dict with a new group looked up each time.
    group = None

    def _updateData(self, json_data):
        """
        Sanity checks the JSON data and retrieves the data for the group specified
        :param json_data: JSON request
        :return: the client_name specified in the JSON to allow the message handler to lookup
        the correct messages within this group.
        """
        self._clear_group()
        if 'client_name' in json_data:
            client_name = json_data['client_name']
        else:
            logging.error("Missing client_name in request: %s" % json_data)
            return None
        if json_data['group_name'] not in self.all_groups:
            print json.dumps(json_data)
            if "group_size" not in json_data or json_data["group_size"] == 0:
                logging.error('%s asked for a new group %s without specifying the size of the group'
                              % (client_name, json_data['group_name']))
                return None
            # auto register a new group
            self.group["count"] = int(json_data["group_size"])
            self.group["group"] = json_data["group_name"]
            self.all_groups[json_data["group_name"]] = self.group
            logging.info("The %s group will contain %d nodes." % (self.group["group"], self.group["count"]))
        self.group = self.all_groups[json_data['group_name']]
        # now add this client to the registered data for this group
        if client_name not in self.group['clients']:
            self.group['clients'][client_name] = json_data['hostname']
            if json_data['role'] not in self.group['roles']:
                self.group['roles'][json_data['role']] = []
                self.group['roles'][json_data['role']].append(client_name)
        return client_name

    def _clear_group(self):
        self.group = {
            'group': '',
            'count': 0,
            'clients': {},
            'roles': {},
            'syncs': {},
            'messages': {}
        }

    def _setGroupData(self, json_data):
        """
        Implements the wait until all clients in this group have connected
        :rtype : None
        :param json_data: incoming JSON request
        """
        if len(self.group['clients']) != self.group['count']:
            logging.info("Waiting for more clients to connect to %s group" % json_data['group_name'])
            # group_data is not complete yet.
            self.transport.loseConnection()
            return
        self.transport.write(json.dumps(self.group))

    def _sendMessage(self, client_name, messageID):
        """
        :param client_name: the client_name to receive the message
        :param messageID: the message index set by lavaSend
        :rtype : None
        """
        if messageID not in self.group['messages'][client_name]:
            logging.error("Unable to find messageID %s" % messageID)
        self.transport.write(json.dumps(self.group['messages'][client_name][messageID]))

    def _getMessage(self, json_data):
        # message value is allowed to be None as long as the message key exists.
        if 'message' not in json_data or 'messageID' not in json_data:
            logging.error("Invalid message request")
        return json_data['message']

    def _getMessageID(self, json_data):
        if 'message' not in json_data or 'messageID' not in json_data:
            logging.error("Invalid message request")
        return json_data['messageID']

    def _badRequest(self):
        self.transport.write('nack')
        self.transport.loseConnection()

    def lavaSync(self, json_data, client_name):
        """
        Global synchronization primitive. Sends a message and waits for the same
        message from all of the other devices.
        """
        messageID = self._getMessageID(json_data)
        if messageID not in self.group['syncs']:
            self.group['syncs'][messageID] = {}
        if len(self.group['syncs'][messageID]) >= self.group['count']:
            self._sendMessage(client_name, messageID)
            self.group['syncs'][messageID].clear()
        else:
            self.group['syncs'][messageID][client_name] = 1
            # list of sync requests is not complete yet.
            self.transport.loseConnection()

    def lavaWaitAll(self, json_data, client_name):
        """
        Waits until all other devices in the group send a message with the given message ID.
        IF <role> is passed, only wait until all devices with that given role send a message.
        """
        messageID = self._getMessageID(json_data)
        if 'role' in json_data:
            for client in self.group['roles'][json_data['role']]:
                if messageID not in self.group['messages'][client]:
                    self.transport.loseConnection()
                    return
        else:
            for client in self.group['clients']:
                if messageID not in self.group['messages'][client]:
                    self.transport.loseConnection()
                    return
        self._sendMessage(client_name, messageID)

    def lavaWait(self, json_data, client_name):
        """
        Waits until any other device in the group sends a message with the given ID.
        This call will block the client until such message is sent, the server continues.
        :param json_data: the JSON request
        :param client_name: the client_name to receive the message
        """
        messageID = self._getMessageID(json_data)
        if messageID not in self.group['messages'][client_name]:
            self.transport.loseConnection()
            return
        self._sendMessage(client_name, messageID)

    def lavaSend(self, json_data):
        """
        A message list won't be seen by the destination until the destination 
        calls lava_wait or lava_wait_all with the messageID
        If lava_wait is called first, the message will be sent when the client reconnects
        """
        message = self._getMessage(json_data)
        messageID = self._getMessageID(json_data)
        for client in self.group['clients']:
            if messageID not in self.group['messages'][client]:
                self.group['messages'][client][messageID] = ()
            self.group['messages'][client][messageID].append(message)

    def dataReceived(self, data):
        """
        Handles all incoming data for the singleton GroupDispatcher
        :param data: the incoming data stream - expected to be JSON
        """
        if not data:
            self._badRequest()
            return
        try:
            json_data = json.loads(data)
        except ValueError:
            self._badRequest()
            return
        request = json_data['request']
        # retrieve the group data for the group which contains this client and get the client name
        # self-register using the group_size, if necessary
        client_name = self._updateData(json_data)
        if not client_name or not self.group['group']:
            self._badRequest()
            return
        if request == 'group_data':
            self._setGroupData(json_data)
        elif request == "lava_sync":
            self.lavaSync(json_data, client_name)
        elif request == 'lava_wait_all':
            self.lavaWaitAll(json_data, client_name)
        elif request == 'lava_wait':
            self.lavaWait(json_data, client_name)
        elif request == 'lava_send':
            self.lavaSend(json_data)
        elif request == "complete":
            logging.info("dispatcher for '%s' communication complete, closing." % client_name)
            self.transport.loseConnection()
        else:
            self._badRequest()
            logging.error("Unrecognised request. Closed connection.")


class NodeFactory(Factory):
    """
    Initialises a connection to be used for all supported groups
    """

    # This class name will be used by the default buildProtocol to create new protocols:
    protocol = MultiNode

    def buildProtocol(self, addr):
        p = self.protocol()
        p.factory = self
        return p


class GroupDispatcher(object):
    reactor_running = False

    def __init__(self, json_data):
        """
        Initialises the GroupDispatcher singleton
        This is idempotent (although it probably does not need to be).
        :param json_data: incoming target_group based data used to determine the port
        """
        if self.reactor_running:
            # nothing more to do
            return
        group_port = 3079
        if 'port' in json_data:
            # only one chance to change the port
            group_port = json_data['port']
        logging.debug("endpoint = TCP4ServerEndpoint(reactor, %d)" % group_port)
        endpoint = TCP4ServerEndpoint(reactor, group_port)
        endpoint.listen(NodeFactory())
        self.reactor_running = True
        reactor.run()

    def stop(self):
        """
        When the initialisation of the GroupDispatcher is in the scheduler,
        the scheduler can close the GroupDispatcher after aggregating the result
        bundles.
        """
        reactor.stop()


def main():
    """
    Only used for local debug.
    """
    with open("/home/neil/code/lava/bundles/group.json") as stream:
        jobdata = stream.read()
        json_jobdata = json.loads(jobdata)
    group = GroupDispatcher(json_jobdata)
    return 0

if __name__ == '__main__':
    main()
