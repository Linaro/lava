from twisted.internet import reactor, defer
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
        'clients': {}
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
        self.group['clients'][client_name] = request
        if request == 'group_data':
            if len(self.group['clients']) != self.group['count']:
                # group_data is not complete yet.
                self.transport.loseConnection()
                return
            self.transport.write(json.dumps(self.group))
        elif request == "complete":
            print "dispatcher for '%s' communication complete, closing." % client_name
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

endpoint = TCP4ServerEndpoint(reactor, 3079)
endpoint.listen(NodeFactory('test', 2))
reactor.run()

