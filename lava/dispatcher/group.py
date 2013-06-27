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
import json
import time
import socket


class GroupDispatcher(object):

    running = False
    delay = 1
    blocksize = 1024
    all_groups = {}
    # FIXME: consider folding this into a data class?
    # All data handling for each connection happens on this local reference into the
    # all_groups dict with a new group looked up each time.
    group = None
    conn = None

    def __init__(self, json_data):
        """
        Initialises the GroupDispatcher singleton
        :param json_data: incoming target_group based data used to determine the port
        """
        self.group_port = 3079
        if 'port' in json_data:
            self.group_port = json_data['port']
        if 'blocksize' in json_data:
            self.blocksize = json_data['blocksize']

    def run(self):
        s = None
        while 1:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                logging.info("binding")
                s.bind(('localhost', self.group_port))
                break
            except socket.error as e:
                logging.warn("Unable to bind, trying again with delay=%d msg=%s" % (self.delay, e.message))
                time.sleep(self.delay)
                self.delay *= 2
        s.listen(1)
        self.running = True
        while self.running:
            logging.info("waiting to accept new connections")
            self.conn, addr = s.accept()
#            logging.info("Connected", addr)
            data = str(self.conn.recv(self.blocksize))
            try:
                json_data = json.loads(data)
            except ValueError:
                logging.warn("JSON error for %s" % data)
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
            self._waitResponse()
            return
        logging.info("Group complete, starting tests")
        self._ackResponse()

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
        logging.info("Sending message '%s' to %s in group %s" % (messageID, client_name, self.group['group']))
        self.conn.send(json.dumps({"response": "ack", "message": self.group['messages'][client_name][messageID]}))
        self.conn.close()
        del self.group['messages'][client_name][messageID]

    def _getMessage(self, json_data):
        # message value is allowed to be None as long as the message key exists.
        if 'message' not in json_data:
            return None
        if 'messageID' not in json_data:
            logging.error("No 'messageID' key found in request %s when looking for message." % json.dumps(json_data))
            return None
        return json_data['message']

    def _getMessageID(self, json_data):
        if 'messageID' not in json_data:
            logging.error("No 'messageID' key found in request %s when looking for ID" % json.dumps(json_data))
            return None
        return json_data['messageID']

    def _badRequest(self):
        self.conn.send(json.dumps({"response": "nack"}))
        self.conn.close()

    def _ackResponse(self):
        self.conn.send(json.dumps({"response": "ack"}))
        self.conn.close()

    def _waitResponse(self):
        self.conn.send(json.dumps({"response": "wait"}))
        self.conn.close()

    def lavaSync(self, json_data, client_name):
        """
        Global synchronization primitive. Sends a message and waits for the same
        message from all of the other devices.
        """
        logging.debug("GroupDispatcher:lavaSync %s from %s in group %s" %(json.dumps(json_data), client_name, self.group['group']))
        messageID = self._getMessageID(json_data)
        message = self._getMessage(json_data)
        # FIXME: in _sendMessage, be sure to send the messageID if message is empty
        if not message:
            message = messageID
        logging.info("LavaSync request for '%s' at stage '%s' in group '%s'" % (client_name, messageID, self.group['group']))
        self.group['syncs'].setdefault(messageID, {})
        self.group['messages'].setdefault(client_name, {}).setdefault(messageID, {})
        if len(self.group['syncs'][messageID]) >= self.group['count']:
            self.group['messages'][client_name][messageID] = message
            self._sendMessage(client_name, messageID)
            # mark this client as having picked up the message
            self.group['syncs'][messageID][client_name] = 0
        else:
            logging.info("waiting: not all clients in group '%s' have been seen yet %d < %d" %
                         (self.group['group'], len(self.group['syncs'][messageID]), self.group['count']))
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
        if 'role' in json_data:
            for client in self.group['roles'][json_data['role']]:
                if messageID not in self.group['messages'][client]:
                    self._waitResponse()
                    return
        else:
            for client in self.group['clients']:
                if messageID not in self.group['messages'][client]:
                    self._waitResponse()
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
            self._waitResponse()
            return
        self._sendMessage(client_name, messageID)

    def lavaSend(self, json_data):
        """
        A message list won't be seen by the destination until the destination
        calls lava_wait or lava_wait_all with the messageID
        If lava_wait is called first, the message will be sent when the client reconnects
        """
        message = self._getMessage(json_data)
        logging.info("lavaSend handler in GroupDispatcher received a message '%s' for group '%s'" % (message, self.group['group']))
        messageID = self._getMessageID(json_data)
        for client in self.group['clients']:
            if messageID not in self.group['messages'][client]:
                self.group['messages'][client][messageID] = []
            self.group['messages'][client][messageID].append(message)

    def dataReceived(self, json_data):
        """
        Handles all incoming data for the singleton GroupDispatcher
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
            self._badRequest()
            return
        if request == 'group_data':
            self._setGroupData(json_data)
        elif request == "lava_sync":
            logging.debug("lava_sync: %s request made by '%s' in group '%s'" %
                          (json.dumps(json_data), client_name, self.group['group']))
            self.lavaSync(json_data, client_name)
        elif request == 'lava_wait_all':
            self.lavaWaitAll(json_data, client_name)
        elif request == 'lava_wait':
            self.lavaWait(json_data, client_name)
        elif request == 'lava_send':
            logging.info("lava_send: %s" % json_data)
            self.lavaSend(json_data)
        elif request == "complete":
            logging.info("dispatcher communication for '%s' in group '%s' is complete, closing." %
                         (client_name, self.group['group']))
            self.conn.close()
        else:
            self._badRequest()
            logging.error("Unrecognised request %s. Closed connection." % json_data)


def main():
    """
    Only used for local debug.
    """
    with open("/home/neil/code/lava/bundles/group.json") as stream:
        jobdata = stream.read()
        json_jobdata = json.loads(jobdata)
    group = GroupDispatcher(json_jobdata)
    group.run()
    return 0

if __name__ == '__main__':
    main()
