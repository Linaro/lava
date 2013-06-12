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
        'syncs': {}
    }

    def setGroupName(self, group_name, count):
        """
        All requests to this server need to be within this group and
        the group itself must have more than 1 member.
        """
        if not group_name:
            raise ValueError("An empty 'group_name' is not supported.")
        self.group['group'] = group_name
        if count < 2:
            raise ValueError("No point using MultiNode with a group count of zero or one.")
        self.group['count'] = count

    def dataReceived(self, data):
        if not self.group['group']:
            # skip if the group is not set.
            self.transport.write('nack')
            self.transport.loseConnection()
        json_data = json.loads(data)
        if 'client_name' in json_data:
            client_name = json_data['client_name']
        else:
            raise ValueError("Missing client_name in request: %s" % data)
        if json_data['group_name'] != self.group['group']:
            raise ValueError('%s tried to send to the wrong server for group %s' % (client_name, json_data['group_name']))
        request =  json_data['request']
        self.group['clients'][client_name] = json_data['hostname']
        if request == 'group_data':
            if len(self.group['clients']) != self.group['count']:
                logging.info("Waiting for more clients to connect to %s group" % json_data['group_name'])
                # group_data is not complete yet.
                self.transport.loseConnection()
                return
            self.transport.write(json.dumps(self.group))
        elif request == "lava_sync":
            if len(self.group['syncs']) >= self.group['count']:
                self.transport.write('ack')
                self.group['syncs'].clear()
            elif len(self.group['syncs']) < self.group['count']:
                self.group['syncs'][client_name] = request
                # list of sync requests is not complete yet.
                self.transport.loseConnection()
                return
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
