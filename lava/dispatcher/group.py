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
    group = {
        'group': '',
        'count': 0,
        'clients': {},
        'roles': {},
        'syncs': {},
        'messages': {}
    }

    def _updateData(self, json_data):
        if 'client_name' in json_data:
            client_name = json_data['client_name']
        else:
            raise ValueError("Missing client_name in request: %s" % json_data)
        if json_data['group_name'] != self.group['group']:
            raise ValueError('%s tried to send to the wrong server for group %s'
                             % (client_name, json_data['group_name']))
        if client_name not in self.group['clients']:
            self.group['clients'][client_name] = json_data['hostname']
            if json_data['role'] not in self.group['roles']:
                self.group['roles'][json_data['role']] = []
                self.group['roles'][json_data['role']].append(client_name)
        return client_name

    def _setGroupData(self, json_data):
        if len(self.group['clients']) != self.group['count']:
            logging.info("Waiting for more clients to connect to %s group" % json_data['group_name'])
            # group_data is not complete yet.
            self.transport.loseConnection()
            return
        self.transport.write(json.dumps(self.group))

    def _sendMessage(self, client_name, messageID):
        if messageID not in self.group['messages'][client_name]:
            raise ValueError("Unable to find messageID %s" % messageID)
        self.transport.write(json.dumps(self.group['messages'][client_name][messageID]))

    def _getMessage(self, json_data):
        # message value is allowed to be None as long as the message key exists.
        if 'message' not in json_data or 'messageID' not in json_data:
            raise ValueError("Invalid message request")
        return json_data['message']

    def _getMessageID(self, json_data):
        if 'message' not in json_data or 'messageID' not in json_data:
            raise ValueError("Invalid message request")
        return json_data['messageID']

    def setGroupName(self, group_name, count):
        """
        All requests to this server need to be within this group and
        the group itself must have more than 1 member.
        """
        if not group_name:
            raise ValueError("An empty 'group_name' is not supported.")
        if count < 2:
            raise ValueError("No point using MultiNode with a group count of zero or one.")
        self.group['group'] = group_name
        self.group['count'] = count

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
        This call will block until such message is sent.
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
        If lava_wait is called first, the message list will be sent in place of the ack.
        """
        message = self._getMessage(json_data)
        messageID = self._getMessageID(json_data)
        for client in self.group['clients']:
            if messageID not in self.group['messages'][client]:
                self.group['messages'][client][messageID] = ()
            self.group['messages'][client][messageID].append(message)

    def dataReceived(self, data):
        if not self.group['group']:
            # skip if the group is not set.
            self.transport.write('nack')
            self.transport.loseConnection()
        json_data = json.loads(data)
        client_name = self._updateData(json_data)
        request = json_data['request']
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
            self.transport.write('nack')
            self.transport.loseConnection()
            raise ValueError("Unrecognised request")


class NodeFactory(Factory):
    """
    Initialises a connection for the specified group
    """

    # This class name will be used by the default buildProtocol to create new protocols:
    protocol = MultiNode
    group_name = ''
    count = 0

    def __init__(self, group_name, count):
        self.group_name = group_name
        self.count = count

    def buildProtocol(self, addr):
        p = self.protocol()
        p.setGroupName(self.group_name, self.count)
        p.factory = self
        return p


class GroupDispatcher(object):

    def __init__(self, json_data):
        """
        Parse the modified JSON to identify the group name,
        requested port for the group - node comms
        and count the number of nodes in this group.
        """
        # FIXME: do this with a schema once the API settles
        if 'target_group' not in json_data:
            raise ValueError("Invalid JSON for a MultiNode GroupDispatcher: no target_group.")
        group_name = json_data['target_group']
        group_port = 3079
        group_count = 0
        if 'port' in json_data:
            group_port = json_data['port']
        for node in json_data['nodes']:
            group_count += int(node['count'])
        logging.info("The %s group will contain %d nodes." % (group_name, group_count))
        logging.debug("endpoint = TCP4ServerEndpoint(reactor, %d)" % group_port)
        logging.debug("endpoint.listen(NodeFactory(\"%s\", %d)" % (group_name, group_count))
        endpoint = TCP4ServerEndpoint(reactor, group_port)
        endpoint.listen(NodeFactory(group_name, group_count))
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
    print json_jobdata
    group = GroupDispatcher(json_jobdata)
    return 0

if __name__ == '__main__':
    main()
