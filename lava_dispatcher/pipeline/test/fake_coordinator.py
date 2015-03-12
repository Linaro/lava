#  Copyright 2013-2014 Linaro Limited
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
import json
import uuid


# disable pylint warnings until lava-coordinator is updated to make it easier to port other changes.
# lava-coordinator would need to be repackaged to make a module package and support a non-socket mode.
# pylint: disable=superfluous-parens,invalid-name,logging-not-lazy,attribute-defined-outside-init,no-self-use


class TestSignals(object):

    message_str = ''

    def formatString(self, reply):
        if type(reply) is dict:
            for target, messages in reply.items():
                for key, value in messages.items():
                    self.message_str += " %s:%s=%s" % (target, key, value)
        return self.message_str

    def checkMessage(self, reply):
        if reply is not None:
            self.log = logging.getLogger("testCase")
            self.log.info("\t<LAVA_TEST_COMPLETE%s>" % self.formatString(reply))


class TestSocket(object):
    """
    Mock up a LavaCoordinator socket without needing a server
    """

    response = None
    header = True
    log = None
    message = None
    passes = 0
    signalHandler = None

    def __init__(self):
        self.log = logging.getLogger("testCase")
        self.signalHandler = TestSignals()
        self.response = None

    def send(self, data):
        if self.header:
            self.header = False
            assert(int(data, 16) < 0xFFFE)
            self.log.info("\tCoordinator header: %d bytes" % int(data, 16))
        else:
            try:
                json_data = json.loads(data)
            except ValueError:
                assert False
            if not self.response:
                assert(json_data['response'] == "nack")
                self.header = True
                return
            assert 'response' in json_data
            self.log.info("\tCoordinator response: '%s'" % json_data['response'])
            self.log.info("\tdebug: %s" % self.response['response'])
            assert(json_data['response'] == self.response['response'])
            self.passes += 1
            if self.message:
                # we are expecting a message back.
                assert 'message' in json_data
                self.log.info("\tCoordinator received a message: '%s'" % (json.dumps(json_data['message'])))
                assert(json_data['message'] == self.message)
                self.passes += 1
            else:
                # actual calls will discriminate between dict and string replies
                # according to the call prototype itself
                if "message" in json_data:
                    if type(json_data['message']) is dict:
                        self.log.info("\tCould have expected a message: '%s'" % json.dumps(json_data['message']))
                    else:
                        self.log.info("\t<LAVA_TEST_REPLY %s>" % json_data['message'])
                self.passes += 1
            self.header = True
            self.response = json_data

    def get_response(self):
        """ Without a socket, need to get the actual response direct
        """
        return self.response

    def close(self):
        self.log.info("\tCoordinator closing.")

    def clearPasses(self):
        self.passes = 0

    def logPasses(self):
        if self.passes == 1:
            self.log.info("\tCoordinator: %d socket test passed" % self.passes)
        else:
            self.log.info("\tCoordinator: %d socket tests passed" % self.passes)

    def prepare(self, name):
        if name:
            self.response = {'response': name}
        if self.response:
            self.log.info("\tCoordinator: expecting a response: '%s'" % self.response['response'])

    def validate(self, message):
        self.message = message
        if self.message:
            self.log.info("\tCoordinator: expecting a message: '%s'" % json.dumps(self.message))
        self.signalHandler.checkMessage(self.message)


class TestCoordinator(object):
    """
    Contains direct copies of critical functions from lava.coordinator module in a wrapper
    which prevents the need for socket communication. Module imported from lava-coordinator 0.1.5
    """

    running = True
    json_data = None
    group_name = None
    group_size = 0
    client_name = None
    conn = None
    log = None
    rpc_delay = 2
    blocksize = 4 * 1024
    host = "localhost"
    all_groups = {}

    def __init__(self):
        self.group_name = str(uuid.uuid4())
        self.conn = TestSocket()
        self.log = logging.getLogger("testCase")
        self.log.info("")
        self.json_data = {"request": "testing"}
        self.client_name = "testpoller"
        self.log.info("\tStarting test with %s %d %d %s" %
                      (json.dumps(self.json_data), self.rpc_delay,
                       self.blocksize, self.host))
        self.expectResponse(None)

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
            raise RuntimeError("Missing client_name in request: %s" % json_data)
        if json_data['group_name'] not in self.all_groups:
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
            'complete': 0,
            'rpc_delay': self.rpc_delay,
            'clients': {},
            'roles': {},
            'syncs': {},
            'messages': {},
            'waits': {},
            'bundles': {}
        }

    def _clearGroupData(self, json_data):
        """
        Clears the group data once all nodes have finished.
        Nodes do *not* wait for other nodes to finish.
        :param json_data: incoming JSON request
        """
        if 'group_name' not in json_data:
            self._badRequest()
            return
        if json_data['group_name'] not in self.all_groups:
            self._badRequest()
            return
        self.group['complete'] += 1
        logging.debug("clear Group Data: %d of %d" % (self.group['complete'], len(self.group['clients'])))
        self._ackResponse()
        if len(self.group['clients']) > self.group['complete']:
            return
        logging.debug("Clearing group data for %s" % json_data['group_name'])
        del self.all_groups[json_data['group_name']]
        self._clear_group()

    def _setGroupData(self, json_data):
        """
        Implements the wait until all clients in this group have connected
        :rtype : None
        :param json_data: incoming JSON request
        """
        if len(self.group['clients']) != self.group['count']:
            logging.info("Waiting for %d more clients to connect to %s group" %
                         ((self.group['count'] - len(self.group['clients']), json_data['group_name'])))
            # group_data is not complete yet.
            self._waitResponse()
            return
        logging.info("Group complete, starting tests")
        # client_name must be unique because it's the DB index & conf file name
        group_data = {}
        for role in self.group['roles']:
            for client in self.group['roles'][role]:
                group_data[client] = role
        msg = {"response": "group_data", "roles": group_data}
        msgdata = self._formatMessage(msg)
        if msgdata:
            self.conn.send(msgdata[0])
            self.conn.send(msgdata[1])
        self.conn.close()

    def _formatMessage(self, message):
        """ Prepares the LAVA Coordinator header and a JSON string
        of the message ready for transmission. Currently, the
        header is just the length of the JSON string as a hexadecimal
        string padded to 8 characters (not including 0x)
        :param message: Python object suitable for conversion into JSON
        :rtype : A tuple - first value is the header, second value is
        the data to send, returns None if the message could not be formatted.
        """
        try:
            msgstr = json.dumps(message)
        except ValueError:
            return None
        # "header" calculation
        msglen = "%08X" % len(msgstr)
        if int(msglen, 16) > 0xFFFFFFFF:
            logging.error("Message was too long to send! %d > %d" %
                          (int(msglen, 16), 0xFFFFFFFF))
            return None
        return msglen, msgstr

    def _sendMessage(self, client_name, messageID):
        """ Sends a message to the currently connected client.
        (the "connection name" or hostname of the connected client does not necessarily
        match the name of the client registered with the group.)
        :param client_name: the client_name to lookup for the message
        :param messageID: the message index set by lavaSend
        :rtype : None
        """
        if client_name not in self.group['messages'] or messageID not in self.group['messages'][client_name]:
            logging.error("Unable to find messageID %s for client %s" % (messageID, client_name))
            self._badRequest()
            return
        logging.info(
            "Sending messageID '%s' to %s in group %s: %s" %
            (messageID, client_name, self.group['group'],
             json.dumps(self.group['messages'][client_name][messageID])))
        msg = {"response": "ack", "message": self.group['messages'][client_name][messageID]}
        msgdata = self._formatMessage(msg)
        if msgdata:
            logging.info("Sending response to %s in group %s: %s" %
                         (client_name, self.group['group'], json.dumps(msg)))
            self.conn.send(msgdata[0])
            self.conn.send(msgdata[1])
        self.conn.close()

    def _sendWaitMessage(self, client_name, messageID):
        """ Sends a wait message to the currently connected client.
        (the "connection name" or hostname of the connected client does not necessarily
        match the name of the client registered with the group.)
        :param client_name: the client_name to lookup for the message
        :param messageID: the message index set by lavaSend
        :rtype : None
        """
        if messageID not in self.group['waits'] or client_name not in self.group['waits'][messageID]:
            logging.error("Unable to find messageID %s for client %s" % (messageID, client_name))
            self._badRequest()
            return
        logging.info("Sending wait messageID '%s' to %s in group %s: %s" %
                     (messageID, client_name, self.group['group'],
                      json.dumps(self.group['waits'][messageID]['data'])))
        msg = {"response": "ack", "message": self.group['waits'][messageID]['data']}
        msgdata = self._formatMessage(msg)
        if msgdata:
            logging.info(
                "Sending wait response to %s in group %s: %s" %
                (client_name, self.group['group'], json.dumps(msg)))
            self.conn.send(msgdata[0])
            self.conn.send(msgdata[1])
        self.conn.close()

    def _getMessage(self, json_data):
        # message value is allowed to be None as long as the message key exists.
        if 'message' not in json_data:
            return {}
        if 'messageID' not in json_data:
            logging.error("No 'messageID' key found in request %s when looking for message." % json.dumps(json_data))
            return {}
        if json_data['message'] is None:
            return {}
        return json_data['message']

    def _getMessageID(self, json_data):
        if 'messageID' not in json_data:
            logging.error("No 'messageID' key found in request %s when looking for ID" % json.dumps(json_data))
            return None
        return json_data['messageID']

    def _badRequest(self):
        msgdata = self._formatMessage({"response": "nack"})
        if msgdata:
            self.conn.send(msgdata[0])
            self.conn.send(msgdata[1])
        self.conn.close()

    def _ackResponse(self):
        msgdata = self._formatMessage({"response": "ack"})
        if msgdata:
            self.conn.send(msgdata[0])
            self.conn.send(msgdata[1])
        self.conn.close()

    def _waitResponse(self):
        msgdata = self._formatMessage({"response": "wait"})
        if msgdata:
            self.conn.send(msgdata[0])
            self.conn.send(msgdata[1])
        self.conn.close()

    def lavaSync(self, json_data, client_name):
        """
        Global synchronization primitive. Sends a message and waits for the same
        message from all of the other devices.
        """
        logging.debug("Coordinator:lavaSync %s from %s in group %s" %
                      (json.dumps(json_data), client_name, self.group['group']))
        messageID = self._getMessageID(json_data)
        message = self._getMessage(json_data)
        # send the messageID as the message if message is empty
        if not message:
            message = messageID
        logging.info("LavaSync request for '%s' at stage '%s' in group '%s'" %
                     (client_name, messageID, self.group['group']))
        self.group['syncs'].setdefault(messageID, {})
        self.group['messages'].setdefault(client_name, {}).setdefault(messageID, {})
        if len(self.group['syncs'][messageID]) >= self.group['count']:
            self.group['messages'][client_name][messageID] = message
            self._sendMessage(client_name, messageID)
            # mark this client as having picked up the message
            self.group['syncs'][messageID][client_name] = 0
        else:
            logging.info("waiting for '%s': not all clients in group '%s' have been seen yet %d < %d" %
                         (messageID, self.group['group'], len(self.group['syncs'][messageID]), self.group['count']))
            self.group['messages'][client_name][messageID] = message
            self.group['syncs'][messageID][client_name] = 1
            self._waitResponse()
            return
        # clear the sync data for this messageID when the last client connects to
        # allow the message to be re-used later for another sync
        clear_syncs = True
        for pending in self.group['syncs'][messageID]:
            if self.group['syncs'][messageID][pending]:
                clear_syncs = False
        if clear_syncs:
            logging.debug("Clearing all sync messages for '%s' in group '%s'" % (messageID, self.group['group']))
            self.group['syncs'][messageID].clear()

    def lavaWaitAll(self, json_data, client_name):
        """
        Waits until all other devices in the group send a message with the given message ID.
        IF <role> is passed, only wait until all devices with that given role send a message.
        """
        logging.debug("lavaWaitAll:json_data: %s" % json_data)
        messageID = self._getMessageID(json_data)
        if 'waitrole' in json_data:
            for client in self.group['roles'][json_data['role']]:
                if messageID not in self.group['waits']:
                    logging.debug("messageID %s not yet seen" % messageID)
                    self._waitResponse()
                    return
                if client not in self.group['waits'][messageID]:
                    # FIXME: bug? if this client has not sent the messageID yet,
                    # causing it to wait will simply force a timeout. node needs
                    # to output a warning, so maybe send a "nack" ?
                    self._waitResponse()
                    return
                if client in self.group['waits']:
                    logging.debug("replying: %s for %s" % (self.group['waits'][client][messageID], client))
            if client_name in self.group['waits']:
                logging.debug("lavaWaitAll message: %s" % json.dumps(self.group['waits'][client_name][messageID]))
        else:
            for client in self.group['clients']:
                logging.debug("checking %s for wait message" % client)
                if messageID not in self.group['waits']:
                    logging.debug("messageID %s not yet seen" % messageID)
                    self._waitResponse()
                    return
                if client not in self.group['waits'][messageID]:
                    logging.debug("setting waiting for %s" % client)
                    self._waitResponse()
                    return
        self._sendWaitMessage(client_name, messageID)

    def lavaWait(self, json_data, client_name):
        """
        Waits until any other device in the group sends a message with the given ID.
        This call will block the client until such message is sent, the server continues.
        :param json_data: the JSON request
        :param client_name: the client_name to receive the message
        """
        messageID = self._getMessageID(json_data)
        if client_name not in self.group['messages'] or messageID not in self.group['messages'][client_name]:
            logging.debug("MessageID %s not yet seen for %s" % (messageID, client_name))
            self._waitResponse()
            return
        self._sendMessage(client_name, messageID)

    def lavaSend(self, json_data, client_name):
        """
        A message list won't be seen by the destination until the destination
        calls lava_wait or lava_wait_all with the messageID
        If lava_wait is called first, the message will be sent when the client reconnects
        messages are broadcast - picked up by lava-wait or lava-sync - any call to lava-wait will pick up
            the complete message.
        waits are not broadcast - only picked up by lava-wait-all - all calls to lava-wait-all will
            wait until all clients have used lava-send for the same messageID
        """
        message = self._getMessage(json_data)
        messageID = self._getMessageID(json_data)
        logging.info("lavaSend handler in Coordinator received a messageID '%s' for group '%s' from %s"
                     % (messageID, self.group['group'], client_name))
        if client_name not in self.group['messages']:
            self.group['messages'][client_name] = {}
        # construct the message hash which stores the data from each client separately
        # but which gets returned as a complete hash upon request
        msg_hash = {}
        msg_hash.update({client_name: message})
        # always set this client data if the call is made to update the broadcast
        if messageID not in self.group['messages'][client_name]:
            self.group['messages'][client_name][messageID] = {}
        self.group['messages'][client_name][messageID].update(msg_hash)
        logging.debug("message %s for %s" % (json.dumps(self.group['messages'][client_name][messageID]), client_name))
        # now broadcast the message into the other clients in this group
        for client in self.group['clients']:
            if client not in self.group['messages']:
                self.group['messages'][client] = {}
            if messageID not in self.group['messages'][client]:
                self.group['messages'][client][messageID] = {}
            self.group['messages'][client][messageID].update(msg_hash)
            logging.debug("broadcast %s for %s" % (json.dumps(self.group['messages'][client][messageID]), client))
        # separate the waits from the messages for wait-all support
        if messageID not in self.group['waits']:
            self.group['waits'][messageID] = {}
        if client_name not in self.group['waits'][messageID]:
            self.group['waits'][messageID][client_name] = {}
        if 'data' not in self.group['waits'][messageID]:
            self.group['waits'][messageID]['data'] = {}
        self.group['waits'][messageID]['data'].update(msg_hash)
        self._ackResponse()

    def dataReceived(self, json_data):
        """
        Handles all incoming data for the singleton LAVA Coordinator
        :param json_data: the incoming data stream - expected to be JSON
        """
        logging.debug("data=%s" % json.dumps(json_data))
        if 'request' not in json_data:
            self._badRequest()
            return
        request = json_data['request']
        # retrieve the group data for the group which contains this client and get the client name
        # self-register using the group_size, if necessary
        client_name = self._updateData(json_data)
        if not client_name or not self.group['group']:
            logging.info("no client_name or group found")
            raise RuntimeError("no client_name or group found")
            # return
        if request == 'group_data':
            self._setGroupData(json_data)
        elif request == "clear_group":
            self._clearGroupData(json_data)
        # elif request == "aggregate":
        #     logging.debug("Aggregate called")
        #     self._aggregateBundle(json_data, client_name)
        elif request == "lava_sync":
            logging.debug("lava_sync: %s request made by '%s' in group '%s'" %
                          (json.dumps(json_data), client_name, self.group['group']))
            self.lavaSync(json_data, client_name)
        elif request == 'lava_wait_all':
            logging.debug("lava_wait_all: %s" % json_data)
            self.lavaWaitAll(json_data, client_name)
        elif request == 'lava_wait':
            logging.debug("lava_wait: %s" % json_data)
            self.lavaWait(json_data, client_name)
        elif request == 'lava_send':
            logging.info("lava_send: %s" % json_data)
            self.lavaSend(json_data, client_name)
        elif request == "complete":
            logging.info("coordinator communication for '%s' in group '%s' is complete, closing." %
                         (client_name, self.group['group']))
            self.conn.close()
        else:
            logging.error("Unrecognised request %s. Closed connection." % json_data)
            self._badRequest()
        return self.conn.get_response()

    def newGroup(self, size):
        self.group_name = str(uuid.uuid4())
        self.group_size = size
        self.log = logging.getLogger("testCase")
        self.log.info("\tGroup name %s" % self.group_name)

    # sets up TestSocket for the correct assertions
    def expectResponse(self, test_name):
        self.conn.prepare(test_name)

    def expectMessage(self, message):
        self.conn.validate(message)

    def addClient(self, client_name):
        self.conn.response = "ack"
        self.client_name = client_name
        self.log = logging.getLogger("testCase")
        ret = self._updateData({"client_name": client_name,
                                "group_size": self.group_size,
                                "role": "tester",
                                "hostname": "localhost",
                                "group_name": self.group_name})
        self.log.info("\tAdded client_name '%s'. group size now: %d" %
                      (client_name, len(self.group['clients'])))
        self.log.info("\tCurrent client_name: '%s'" % self.client_name)
        return ret

    def addClientRole(self, client_name, role):
        self.conn.response = "ack"
        self.client_name = client_name
        self.log = logging.getLogger("testCase")
        ret = self._updateData({"client_name": client_name,
                                "group_size": self.group_size,
                                "role": role,
                                "hostname": "localhost",
                                "group_name": self.group_name})
        self.log.info("\tAdded client_name '%s' with role '%s'. group size now: %d" %
                      (client_name, role, len(self.group['clients'])))
        self.log.info("\tCurrent client_name: '%s'" % self.client_name)
        return ret
