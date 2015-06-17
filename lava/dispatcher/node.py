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

import socket
from socket import gethostname
import json
import errno
import logging
import os
import copy
import sys
import time
from lava_dispatcher.config import get_config
from lava_dispatcher.job import LavaTestJob


class Poller(object):
    """
    Blocking, synchronous socket poller which repeatedly tries to connect
    to the Coordinator, get a very fast response and then implement the
    wait.
    If the node needs to wait, it will get a {"response": "wait"}
    If the node should stop polling and send data back to the board, it will
    get a {"response": "ack", "message": "blah blah"}
    """

    json_data = None
    blocks = 4 * 1024
    # how long between polls (in seconds)
    poll_delay = 1
    timeout = 0

    def __init__(self, data_str):
        try:
            self.json_data = json.loads(data_str)
        except ValueError:
            logging.error("bad JSON")
            exit(1)
        if 'port' not in self.json_data:
            logging.error("Misconfigured NodeDispatcher - port not specified")
        if 'blocksize' not in self.json_data:
            logging.error("Misconfigured NodeDispatcher - blocksize not specified")
        self.blocks = int(self.json_data['blocksize'])
        if "poll_delay" in self.json_data:
            self.poll_delay = int(self.json_data["poll_delay"])
        if 'timeout' in self.json_data:
            self.timeout = self.json_data['timeout']

    def poll(self, msg_str):
        """
        Blocking, synchronous polling of the Coordinator on the configured port.
        Single send operations greater than 0xFFFF are rejected to prevent truncation.
        :param msg_str: The message to send to the Coordinator, as a JSON string.
        :return: a JSON string of the response to the poll
        """
        # starting value for the delay between polls
        delay = 1
        msg_len = len(msg_str)
        if msg_len > 0xFFFE:
            logging.error("Message was too long to send!")
            return
        c = 0
        waited = 0
        response = None
        while True:
            c += self.poll_delay
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.connect((self.json_data['host'], self.json_data['port']))
                logging.debug("Connecting to LAVA Coordinator on %s:%s",
                              self.json_data['host'], self.json_data['port'])
                delay = self.poll_delay
            except socket.error as e:
                if e.errno == errno.ECONNREFUSED:
                    logging.warning("Lava Coordinator refused connection on %s %s" %
                                    (self.json_data['host'], self.json_data['port']))
                elif e.errno == errno.ECONNRESET:
                    logging.warning("Connection to coordinator reset by peer on port %s" %
                                    self.json_data['port'])
                else:
                    logging.warning("socket error on connect: %d %s %s" %
                                    (e.errno, self.json_data['host'], self.json_data['port']))
                logging.debug("Trying again in %s seconds. Job will timeout in %s seconds" %
                              (delay, self.json_data['timeout'] - waited))
                waited += delay
                time.sleep(delay)
                if waited >= self.json_data['timeout']:
                    logging.info("Connection to coordinator timed out")
                    break
                delay += 2
                s.close()
                continue
            logging.debug("sending message: %s...", msg_str[:42])
            # blocking synchronous call
            try:
                # send the length as 32bit hexadecimal
                ret_bytes = s.send("%08X" % msg_len)
                if ret_bytes == 0:
                    logging.debug("zero bytes sent for length - connection closed?")
                    continue
                ret_bytes = s.send(msg_str)
                if ret_bytes == 0:
                    logging.debug("zero bytes sent for message - connection closed?")
                    continue
            except socket.error as e:
                logging.warning("socket error '%d' on send", e.message)
                s.close()
                continue
            s.shutdown(socket.SHUT_WR)
            try:
                header = s.recv(8)  # 32bit limit as a hexadecimal
                if not header or header == '':
                    logging.debug("empty header received?")
                    continue
                msg_count = int(header, 16)
                recv_count = 0
                response = ''
                while recv_count < msg_count:
                    response += s.recv(self.blocks)
                    recv_count += self.blocks
            except socket.error as e:
                logging.warning("socket error '%d' on response", e.errno)
                s.close()
                continue
            s.close()
            if not response:
                time.sleep(delay)
                # if no response, wait and try again
                logging.debug("failed to get a response, setting a wait")
                response = json.dumps({"response": "wait"})
            try:
                json_data = json.loads(response)
            except ValueError:
                logging.error("response starting '%s' was not JSON", response[:42])
                break
            if json_data['response'] != 'wait':
                break
            else:
                if not (c % int(10 * self.poll_delay)):
                    logging.info("Waiting ... %d of %d secs", c, self.timeout)
                time.sleep(delay)
            # apply the default timeout to each poll operation.
            if c > self.timeout:
                response = json.dumps({"response": "nack"})
                break
        return response


def readSettings(filename):
    """
    NodeDispatchers need to use the same port and blocksize as the Coordinator,
    so read the same conffile.
    The protocol header is hard-coded into the server & here.
    """
    settings = {
        "port": 3079,
        "blocksize": 4 * 1024,
        "poll_delay": 1,
        "coordinator_hostname": "localhost"
    }
    with open(filename) as stream:
        jobdata = stream.read()
        json_default = json.loads(jobdata)
    if "port" in json_default:
        settings['port'] = json_default['port']
    if "blocksize" in json_default:
        settings['blocksize'] = json_default["blocksize"]
    if "poll_delay" in json_default:
        settings['poll_delay'] = json_default['poll_delay']
    if "coordinator_hostname" in json_default:
        settings['coordinator_hostname'] = json_default['coordinator_hostname']
    return settings


class NodeDispatcher(object):

    group_name = ''
    client_name = ''
    group_size = 0
    target = ''
    role = ''
    poller = None
    oob_file = sys.stderr
    output_dir = None
    base_msg = None
    json_data = None
    vm_host_ip = None
    is_dynamic_vm = False

    def __init__(self, json_data, oob_file=sys.stderr, output_dir=None):
        """
        Parse the modified JSON to identify the group name,
        requested port for the group - node comms
        and get the designation for this node in the group.
        """
        settings = readSettings("/etc/lava-coordinator/lava-coordinator.conf")
        self.json_data = json_data
        # FIXME: do this with a schema once the API settles
        if 'target_group' not in json_data:
            raise ValueError("Invalid JSON to work with the MultiNode Coordinator: no target_group.")
        self.group_name = json_data['target_group']
        if 'group_size' not in json_data:
            raise ValueError("Invalid JSON to work with the Coordinator: no group_size")
        self.group_size = json_data["group_size"]
        if 'target' not in json_data:
            raise ValueError("Invalid JSON for a child node: no target designation.")
        self.target = json_data['target']
        if 'timeout' not in json_data:
            raise ValueError("Invalid JSON - no default timeout specified.")
        if "sub_id" not in json_data:
            logging.info("Error in JSON - no sub_id specified. Results cannot be aggregated.")
            json_data['sub_id'] = None
        if 'port' in json_data:
            # lava-coordinator provides a conffile for the port and blocksize.
            logging.debug("Port is no longer supported in the incoming JSON. Using %d", settings["port"])
        if 'role' in json_data:
            self.role = json_data['role']
        # look for a vm temporary device - vm_host is managed in boot_linaro_image.
        if 'is_vmhost' in json_data and not json_data['is_vmhost']:
            self.is_dynamic_vm = True
        # hostname of the server for the connection.
        if 'hostname' in json_data:
            # lava-coordinator provides a conffile for the group_hostname
            logging.debug("Coordinator hostname is no longer supported in the incoming JSON. Using %s",
                          settings['coordinator_hostname'])
        self.base_msg = {"port": settings['port'],
                         "blocksize": settings['blocksize'],
                         "poll_delay": settings["poll_delay"],
                         "timeout": json_data['timeout'],
                         "host": settings['coordinator_hostname'],
                         "client_name": json_data['target'],
                         "group_name": json_data['target_group'],
                         # hostname here is the node hostname, not the server.
                         "hostname": gethostname(),
                         "role": self.role,
                         }
        self.client_name = json_data['target']
        self.poller = Poller(json.dumps(self.base_msg))
        self.oob_file = oob_file
        self.output_dir = output_dir
        self.job = None

    def run(self):
        """
        Initialises the node into the group, registering the group if necessary
        (via group_size) and *waiting* until the rest of the group nodes also
        register before starting the actual job,
        Temporary devices in a vm_group do not begin running tests until
        the host is ready.
        """
        jobdata = json.dumps(self.json_data)
        config = get_config()
        if 'logging_level' in self.json_data:
            logging.root.setLevel(self.json_data["logging_level"])
        else:
            logging.root.setLevel(config.logging_level)
        # create the job so that logging is enabled, start the job later.
        self.job = LavaTestJob(jobdata, self.oob_file, config, self.output_dir)
        init_msg = {"request": "group_data", "group_size": self.group_size}
        init_msg.update(self.base_msg)
        logging.info("Starting Multi-Node communications for group '%s'", self.group_name)
        logging.debug("init_msg %s", json.dumps(init_msg))
        response = json.loads(self.poller.poll(json.dumps(init_msg)))
        logging.info("Starting the test run for %s in group %s", self.client_name, self.group_name)

        # if this is a temporary device, wait for lava_vm_start from host
        # before starting job
        if self.is_dynamic_vm:
            logging.info("Waiting for host IP address ...")
            host_info = self.request_wait("lava_vm_start")  # blocking call
            host_data = json.loads(host_info)["message"]
            logging.info("Host data: %r", host_data)
            for host in host_data:
                self.vm_host_ip = host_data[host]['host_ip']
                logging.info("Host %s has IP address %s", host, self.vm_host_ip)

        self.run_tests(self.json_data, response)
        # send a message to the GroupDispatcher to close the group (when all nodes have sent fin_msg)
        fin_msg = {"request": "clear_group", "group_size": self.group_size}
        fin_msg.update(self.base_msg)
        logging.debug("fin_msg %s", json.dumps(fin_msg))
        self.poller.poll(json.dumps(fin_msg))

    def __call__(self, args):
        """ Makes the NodeDispatcher callable so that the test shell can send messages just using the
        NodeDispatcher object.
        This function blocks until the specified API call returns. Some API calls may involve a
        substantial period of polling.
        :param args: JSON string of the arguments of the API call to make
        :return: A Python object containing the reply dict from the API call
        """
        try:
            return self._select(json.loads(args))
        except KeyError:
            logging.warning("Unable to handle request for: %s", args)

    def _select(self, json_data):
        """ Determines which API call has been requested, makes the call, blocks and returns the reply.
        :param json_data: Python object of the API call
        :return: Python object containing the reply dict.
        """
        reply_str = ''
        if not json_data:
            logging.debug("Empty args")
            return
        if 'request' not in json_data:
            logging.debug("Bad call")
            return
        if json_data["request"] == "aggregate":
            # no message processing here, just the bundles.
            return self._aggregation(json_data)
        messageID = json_data['messageID']
        if json_data['request'] == "lava_sync":
            logging.info("requesting lava_sync '%s'", messageID)
            reply_str = self.request_sync(messageID)
        elif json_data['request'] == 'lava_wait':
            logging.info("requesting lava_wait '%s'", messageID)
            reply_str = self.request_wait(messageID)
        elif json_data['request'] == 'lava_wait_all':
            if 'role' in json_data and json_data['role'] is not None:
                reply_str = self.request_wait_all(messageID, json_data['role'])
                logging.info("requesting lava_wait_all '%s' '%s'", messageID, json_data['role'])
            else:
                logging.info("requesting lava_wait_all '%s'", messageID)
                reply_str = self.request_wait_all(messageID)
        elif json_data['request'] == "lava_send":
            logging.info("requesting lava_send %s", messageID)
            reply_str = self.request_send(messageID, json_data['message'])
        reply = json.loads(str(reply_str))
        if 'message' in reply:
            return reply['message']
        else:
            return reply['response']

    def _aggregation(self, json_data):
        """ Internal call to send the bundle message to the coordinator so that the node
        with sub_id zero will get the complete bundle and everyone else a blank bundle.
        :param json_data: Arbitrary data from the job which will form the result bundle
        """
        if json_data["bundle"] is None:
            logging.info("Notifying LAVA Coordinator of job completion")
        else:
            logging.info("Passing results bundle to LAVA Coordinator.")
        reply_str = self._send(json_data)
        reply = json.loads(str(reply_str))
        if 'message' in reply:
            return reply['message']
        else:
            return reply['response']

    def _send(self, msg):
        """ Internal call to perform the API call via the Poller.
        :param msg: The call-specific message to be wrapped in the base_msg primitive.
        :return: Python object of the reply dict.
        """
        new_msg = copy.deepcopy(self.base_msg)
        new_msg.update(msg)
        if 'bundle' in new_msg:
            logging.debug("sending result bundle")
        else:
            logging.debug("sending Message %s", json.dumps(new_msg))
        return self.poller.poll(json.dumps(new_msg))

    def request_wait_all(self, messageID, role=None):
        """
        Asks the Coordinator to send back a particular messageID
        and blocks until that messageID is available for all nodes in
        this group or all nodes with the specified role in this group.
        """
        # FIXME: if this node has not called request_send for the
        # messageID used for a wait_all, the node should log a warning
        # of a broken test definition.
        if role:
            return self._send({"request": "lava_wait_all",
                               "messageID": messageID,
                               "waitrole": role})
        else:
            return self._send({"request": "lava_wait_all",
                              "messageID": messageID})

    def request_wait(self, messageID):
        """
        Asks the Coordinator to send back a particular messageID
        and blocks until that messageID is available for this node
        """
        # use self.target as the node ID
        wait_msg = {"request": "lava_wait",
                    "messageID": messageID,
                    "nodeID": self.target}
        return self._send(wait_msg)

    def request_send(self, messageID, message):
        """
        Sends a message to the group via the Coordinator. The
        message is guaranteed to be available to all members of the
        group. The message is only picked up when a client in the group
        calls lava_wait or lava_wait_all.
        The message needs to be formatted JSON, not a simple string.
        { "messageID": "string", "message": { "key": "value"} }
        The message can consist of just the messageID:
        { "messageID": "string" }
        """
        send_msg = {"request": "lava_send",
                    "messageID": messageID,
                    "message": message}
        return self._send(send_msg)

    def request_sync(self, msg):
        """
        Creates and send a message requesting lava_sync
        """
        sync_msg = {"request": "lava_sync", "messageID": msg}
        return self._send(sync_msg)

    def run_tests(self, json_jobdata, group_data):
        if 'response' in group_data and group_data['response'] == 'nack':
            logging.error("Unable to initiliase a Multi-Node group - timed out waiting for other devices.")
            return
        if 'target' not in json_jobdata:
            logging.error("The job file does not specify a target device.")
            exit(1)
        # pass this NodeDispatcher down so that the lava_test_shell can __call__ nodeTransport to write a message
        self.job.run(self, group_data, vm_host_ip=self.vm_host_ip)
