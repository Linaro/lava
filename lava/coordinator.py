import time
import socket
import logging
import json

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


class LavaCoordinator(object):

    running = False
    delay = 1
    rpc_delay = 2
    blocksize = 4 * 1024
    all_groups = {}
    # All data handling for each connection happens on this local reference into the
    # all_groups dict with a new group looked up each time.
    group = None
    conn = None
    host = "localhost"

    def __init__(self, json_data):
        """
        Initialises the LAVA Coordinator singleton
        A single Coordinator serves all groups managed by a lava-server or lab, including
        supporting groups across different instances, if that is desired. Different
        coordinators on one machine must run on different ports.
        :param json_data: incoming target_group based data used to determine the port
        """
        self.group_port = 3079
        if 'port' in json_data:
            self.group_port = json_data['port']
        if 'blocksize' in json_data:
            self.blocksize = json_data['blocksize']
        if 'host' in json_data:
            self.host = json_data['host']

    def run(self):
        s = None
        while 1:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                logging.debug("binding to %s:%s" % (self.host, self.group_port))
                s.bind(('0.0.0.0', self.group_port))
                break
            except socket.error as e:
                logging.warn("Unable to bind, trying again with delay=%d msg=%s" % (self.delay, e.message))
                time.sleep(self.delay)
                self.delay *= 2
        s.listen(1)
        self.running = True
        while self.running:
            logging.info("Ready to accept new connections")
            self.conn, addr = s.accept()
            # read the header to get the size of the message to follow
            data = str(self.conn.recv(8))  # 32bit limit
            try:
                count = int(data, 16)
            except ValueError:
                logging.debug("Invalid message: %s from %s" % (data, self.conn.getpeername()[0]))
                self.conn.close()
                continue
            c = 0
            data = ''
            # get the message itself
            while c < count:
                data += self.conn.recv(self.blocksize)
                c += self.blocksize
            try:
                json_data = json.loads(data)
            except ValueError:
                logging.warn("JSON error for '%s'" % data[:100])
                self.conn.close()
                continue
            self.dataReceived(json_data)

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
        logging.info("Sending messageID '%s' to %s in group %s: %s" %
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
            logging.info("Sending wait response to %s in group %s: %s" %
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

    def _aggregateBundle(self, json_data, client_name):
        """ *All* nodes must call aggregate, even if there is no bundle
        to submit from this board.
        :param json_data: the request header and the bundle itself
        :param client_name: the board identifier in the group data
        """
        if "bundle" not in json_data:
            logging.debug("Aggregate called without a bundle in the JSON")
            self._badRequest()
            return
        if "sub_id" not in json_data or json_data["sub_id"] is None:
            logging.debug("Aggregation called without a valid sub_id in the JSON")
            self._badRequest()
            return
        self.group['bundles'][client_name] = json_data["bundle"]
        if json_data["sub_id"].endswith(".0"):
            logging.info("len:%d count:%d" % (len(self.group['bundles']), self.group['count']))
            if len(self.group['bundles']) < self.group['count']:
                logging.info("Waiting for the rest of the group to complete the job.")
                self._waitResponse()
                self.group['rpc_delay'] = self.rpc_delay
            else:
                # xmlrpc can take time, so allow the last node to submit before finishing the group
                if self.group['rpc_delay'] > 0:
                    logging.debug("Asking sub_id zero to pause while a pending XMLRPC call is made.")
                    self._waitResponse()
                    self.group['rpc_delay'] -= 1
                    return
                logging.debug("Sending bundle list to sub_id zero")
                msg = {"response": "ack", "message": {"bundle": self.group['bundles']}}
                msgdata = self._formatMessage(msg)
                if msgdata:
                    self.conn.send(msgdata[0])
                    self.conn.send(msgdata[1])
                self.group['rpc_delay'] = self.rpc_delay
                self.conn.close()
        else:
            logging.debug("not sub_id zero")
            self._ackResponse()

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
        messageID = self._getMessageID(json_data)
        if 'waitrole' in json_data:
            expected = self.group['roles'][json_data['waitrole']]
            expected = expected[0] if type(expected) == list else None
            logging.debug(
                "lavaWaitAll waiting for role:%s from %s" % (
                    json_data['waitrole'],
                    expected)
            )
            for client in self.group['roles'][json_data['role']]:
                logging.debug("checking %s for wait message" % client)
                if messageID not in self.group['waits']:
                    logging.debug("messageID %s not yet seen" % messageID)
                    self._waitResponse()
                    return
                if expected and expected in self.group['waits'][messageID]:
                    logging.debug("Replying that %s has sent %s" % (client_name, messageID))
                    self._sendWaitMessage(client_name, messageID)
                    return
                if client not in self.group['waits'][messageID]:
                    logging.debug("FIXME: %s not in waits for %s: %s" % (
                        client, messageID, self.group['waits'][messageID]))
                    # FIXME: bug? if this client has not sent the messageID yet,
                    # causing it to wait will simply force a timeout. node needs
                    # to output a warning, so maybe send a "nack" ?
                    self._waitResponse()
                    return
                if client in self.group['waits']:
                    logging.debug("Replying: %s for %s" % (messageID, client_name))
            if client_name in self.group['waits']:
                logging.debug("lavaWaitAll message: %s" % json.dumps(self.group['waits'][client_name][messageID]))
        else:
            logging.debug("lavaWaitAll: no role.")
            for client in self.group['clients']:
                logging.debug("checking %s for wait message" % client)
                if messageID not in self.group['waits']:
                    self._badRequest()
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
        if 'request' not in json_data:
            logging.debug("bad data=%s" % json.dumps(json_data))
            self._badRequest()
            return
        request = json_data['request']
        # retrieve the group data for the group which contains this client and get the client name
        # self-register using the group_size, if necessary
        client_name = self._updateData(json_data)
        if not client_name or not self.group['group']:
            logging.info("no client_name or group found")
            self._badRequest()
            return
        if request == 'group_data':
            self._setGroupData(json_data)
        elif request == "clear_group":
            self._clearGroupData(json_data)
        elif request == "aggregate":
            logging.debug("Aggregate called")
            self._aggregateBundle(json_data, client_name)
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
