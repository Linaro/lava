# Copyright (C) 2015 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.


import copy
import time
import json
import socket
import logging
from lava_dispatcher.pipeline.connection import Protocol
from lava_dispatcher.pipeline.action import JobError, TestError
from lava_dispatcher.pipeline.protocols.multinode import MultinodeProtocol
from lava_dispatcher.pipeline.utils.constants import VLAND_DEPLOY_TIMEOUT


# pylint: disable=too-many-instance-attributes


class VlandProtocol(Protocol):
    """
    VLANd protocol - multiple vlans are possible per group
    Can only run *after* the multinode protocol is ready
    Using the VLANd protocol has hardware and lab topology requirements.
    All workers *must* be able to see a single vland daemon for this instance.
    All workers and all devices *must* be on a single set of managed switches
    which are already configured in that vland daemon. All switches in the set
    *must* be able to setup a vlan that could potentially use ports on any switch
    in the configured set - so each needs to be able to see all of the others.
    """
    name = "lava-vland"
    level = 5

    def __init__(self, parameters, job_id):
        super(VlandProtocol, self).__init__(parameters, job_id)
        self.logger = logging.getLogger('dispatcher')
        self.vlans = {}
        self.ports = []
        self.names = {}
        self.base_group = parameters['protocols'][MultinodeProtocol.name]['target_group'].replace('-', '')[:10]
        self.sub_id = parameters['protocols'][MultinodeProtocol.name]['sub_id']
        self.fake_run = False
        self.settings = None
        self.blocks = 4 * 1024
        self.sock = None
        self.base_message = {}
        self.params = {}
        self.nodes_seen = []  # node == combination of switch & port
        self.multinode_protocol = None

    @classmethod
    def accepts(cls, parameters):
        if 'protocols' not in parameters:
            return False
        if 'lava-multinode' not in parameters['protocols']:
            return False
        if 'target_group' not in parameters['protocols'][MultinodeProtocol.name]:
            return False
        if 'lava-vland' not in parameters['protocols']:
            return False
        return True

    def read_settings(self):  # pylint: disable=no-self-use
        # FIXME: support config file
        settings = {
            "port": 3080,
            "poll_delay": 1,
            "vland_hostname": "localhost"
        }
        return settings

    def _connect(self, delay):
        """
        create socket and connect
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.connect((self.settings['vland_hostname'], self.settings['port']))
            return True
        except socket.error as exc:
            self.logger.exception(
                "socket error on connect: %d %s %s",
                exc.errno, self.settings['vland_hostname'], self.settings['port'])
            time.sleep(delay)
            self.sock.close()
            return False

    def _send_message(self, message):
        msg_len = len(message)
        try:
            # send the length as 32bit hexadecimal
            ret_bytes = self.sock.send("%08X" % msg_len)
            if ret_bytes == 0:
                self.logger.debug("zero bytes sent for length - connection closed?")
                return False
            ret_bytes = self.sock.send(message)
            if ret_bytes == 0:
                self.logger.debug("zero bytes sent for message - connection closed?")
                return False
        except socket.error as exc:
            self.logger.exception("socket error '%d' on send", exc.message)
            self.sock.close()
            return False
        return True

    def _recv_message(self):
        try:
            header = self.sock.recv(8)  # 32bit limit as a hexadecimal
            if not header or header == '':
                self.logger.debug("empty header received?")
                return json.dumps({"response": "wait"})
            msg_count = int(header, 16)
            recv_count = 0
            response = ''
            while recv_count < msg_count:
                response += self.sock.recv(self.blocks)
                recv_count += self.blocks
        except socket.error as exc:
            self.logger.exception("socket error '%d' on response", exc.errno)
            self.sock.close()
            return json.dumps({"response": "wait"})
        return response

    def poll(self, message, timeout=None):
        """
        Blocking, synchronous polling of VLANd on the configured port.
        Single send operations greater than 0xFFFF are rejected to prevent truncation.
        :param msg_str: The message to send to VLAND, as a JSON string.
        :return: a JSON string of the response to the poll
        """
        if not timeout:
            timeout = self.poll_timeout.duration
        msg_len = len(message)
        if msg_len > 0xFFFE:
            raise JobError("Message was too long to send!")
        c_iter = 0
        response = None
        delay = self.settings['poll_delay']
        self.logger.debug("Connecting to VLANd on %s:%s timeout=%d seconds.",
                          self.settings['vland_hostname'], self.settings['port'], timeout)
        while True:
            c_iter += self.settings['poll_delay']
            if self._connect(delay):
                delay = self.settings['poll_delay']
            else:
                delay += 2
                continue
            if not c_iter % int(10 * self.settings['poll_delay']):
                self.logger.debug("sending message: %s waited %s of %s seconds",
                                  json.loads(message)['request'], c_iter, int(timeout))
            # blocking synchronous call
            if not self._send_message(message):
                continue
            self.sock.shutdown(socket.SHUT_WR)
            response = self._recv_message()
            self.sock.close()
            try:
                json_data = json.loads(response)
            except ValueError:
                self.logger.debug("response starting '%s' was not JSON", response[:42])
                self.finalise_protocol()
                break
            if json_data['response'] != 'wait':
                break
            else:
                time.sleep(delay)
            # apply the default timeout to each poll operation.
            if c_iter > timeout:
                self.finalise_protocol()
                raise JobError("protocol %s timed out" % self.name)
        return response

    def _call_vland(self, msg):
        """ Internal call to perform the API call via the Poller.
        :param msg: The call-specific message to be wrapped in the base_msg primitive.
        :param timeout: Number of seconds for this call.
        :return: Python object of the reply dict.
        """
        new_msg = copy.deepcopy(self.base_message)
        new_msg.update(msg)
        self.logger.debug("final message: %s", json.dumps(new_msg))
        return self.poll(json.dumps(new_msg))

    def _create_vlan(self, friendly_name):
        """
        Ask vland to create a vlan which we will track using the friendly_name
        but which vland knows as a generated string in self.names which is
        known to be safe to use on the supported switches.
        Passes -1 as the tag so that vland allocates the next available tag.
        :param friendly_name: user-specified string used to lookup vlan data
        :return: a tuple containing the internal name used by vland and the vland tag.
        """
        msg = {
            'type': 'vlan_update',
            'command': 'api.create_vlan',
            'data': {
                'name': self.names[friendly_name],
                'tag': -1,
                'is_base_vlan': False
            }
        }
        self.logger.debug({"create_vlan": msg})
        response = self._call_vland(msg)
        if not response or response == '':
            return (None, None)
        reply = json.loads(response)
        if 'data' in reply:
            return reply['data']
        raise RuntimeError(reply)

    def _declare_created(self, friendly_name, tag):
        if not self.configured:
            return False
        send_msg = {
            'request': 'lava_send',
            'timeout': VLAND_DEPLOY_TIMEOUT,
            'messageID': friendly_name,
            'message': {
                'vlan_name': self.vlans[friendly_name],
                'vlan_tag': tag
            }
        }
        self.multinode_protocol(send_msg)

    def _wait_on_create(self, friendly_name):
        if not self.configured:
            return False
        wait_msg = {
            'request': 'lava_wait',
            'timeout': VLAND_DEPLOY_TIMEOUT,
            'messageID': friendly_name,
        }
        ret = self.multinode_protocol(wait_msg)
        if ret:
            values = list(ret.values())[0]
            return (values['vlan_name'], values['vlan_tag'],)
        raise JobError("Waiting for vlan creation failed: %s", ret)

    def _delete_vlan(self, friendly_name, vlan_id):
        msg = {
            'type': 'vlan_update',
            'command': 'api.delete_vlan',
            'data': {
                'vlan_id': vlan_id,
            }
        }
        self.logger.debug({"delete_vlan": msg})
        self._call_vland(msg)
        # FIXME detect a failure
        del self.vlans[friendly_name]

    def _lookup_switch_id(self, switch_name):
        msg = {
            'type': 'db_query',
            'command': 'db.get_switch_id_by_name',
            'data': {
                'name': switch_name
            }
        }
        self.logger.debug({"lookup_switch": msg})
        response = self._call_vland(msg)
        if not response or response == '':
            raise JobError("Switch_id for switch name: %s not found", switch_name)
        reply = json.loads(response)
        return reply['data']

    def _lookup_port_id(self, switch_id, port):
        msg = {
            'type': 'db_query',
            'command': 'db.get_port_by_switch_and_number',
            'data': {
                'switch_id': switch_id,
                'number': port
            }
        }
        self.logger.debug({"lookup_port_id": msg})
        response = self._call_vland(msg)
        if not response or response == '':
            raise JobError("Port_id for port: %s not found", port)
        reply = json.loads(response)
        return reply['data']

    def _set_port_onto_vlan(self, vlan_id, port_id):
        msg = {
            'type': 'vlan_update',
            'command': 'api.set_current_vlan',
            'data': {
                'port_id': port_id,
                'vlan_id': vlan_id
            }
        }
        self.logger.debug({"set_port_onto_vlan": msg})
        self._call_vland(msg)
        # FIXME detect a failure

    def _restore_port(self, port_id):
        msg = {
            'type': 'vlan_update',
            'command': 'api.restore_base_vlan',
            'data': {
                'port_id': port_id,
            }
        }
        self.logger.debug({"restore_port": msg})
        self._call_vland(msg)
        # FIXME detect a failure

    def set_up(self):
        """
        Called by Job.run() to initialise the protocol itself.
        The vlan is not setup at the start of the job as the job will likely need networking
        to make the deployment.
        """
        self.settings = self.read_settings()
        self.base_message = {
            "port": self.settings['port'],
            "poll_delay": self.settings["poll_delay"],
            "host": self.settings['vland_hostname'],
            "client_name": socket.gethostname(),
        }

    def configure(self, device, job):  # pylint: disable=too-many-branches
        """
        Called by job.validate() to populate internal data
        Configures the vland protocol for this job for the assigned device.
        Returns True if configuration completed.
        """
        if self.configured:
            return True
        if not device:
            self.errors = "Unable to configure protocol without a device"
        elif 'parameters' not in device:
            self.errors = "Invalid device configuration, no parameters given."
        elif 'interfaces' not in device['parameters']:
            self.errors = "Device lacks interfaces information."
        elif not isinstance(device['parameters']['interfaces'], dict):
            self.errors = "Invalid interfaces dictionary for device"
        protocols = [protocol for protocol in job.protocols if protocol.name == MultinodeProtocol.name]
        if not protocols:
            self.errors = "Unable to determine Multinode protocol object"
        self.multinode_protocol = protocols[0]
        if not self.valid:
            return False
        interfaces = [interface for interface, _ in device['parameters']['interfaces'].items()]
        available = []
        for iface in interfaces:
            if device['parameters']['interfaces'][iface]['tags']:
                # skip primary interfaces
                available.extend(device['parameters']['interfaces'][iface]['tags'])
        requested = []
        for friendly_name in self.parameters['protocols'][self.name]:
            if friendly_name == 'yaml_line':
                continue
            base_jobid = "%s" % job.job_id
            base = "%s%s" % (base_jobid[-8:], friendly_name[:8])
            self.names[friendly_name] = ''.join(e for e in base if e.isalnum())[:16]
        self.params = copy.deepcopy(self.parameters['protocols'][self.name])
        for vlan_name in self.params:
            if vlan_name == 'yaml_line':
                continue
            if 'tags' not in self.params[vlan_name]:
                self.errors = "%s already configured for %s" % (device['hostname'], self.name)
            else:
                requested.extend(self.params[vlan_name]['tags'])
        if set(available) & set(requested) != set(requested):
            self.errors = "Requested link speeds %s are not available %s for %s" % (
                requested, available, device['hostname'])
        if not self.valid:
            return False

        # one vlan_name, one combination of switch & port, one interface, any supported link speed.
        # this may need more work with more complex vlan jobs
        for vlan_name in self.params:
            if vlan_name == 'yaml_line':
                continue
            for iface in interfaces:
                device_info = device['parameters']['interfaces'][iface]
                if ' '.join([device_info['switch'], str(device_info['port'])]) in self.nodes_seen:
                    # combination of switch & port already processed for this device
                    continue
                if not device_info['tags']:
                    # primary network interface, must not allow a vlan
                    continue
                # device interface tags & job tags must equal job tags
                # device therefore must support all job tags, not all job tags available on the device need to be specified
                if set(device_info['tags']) & set(self.params[vlan_name]['tags']) == set(self.params[vlan_name]['tags']):
                    self.params[vlan_name]['switch'] = device_info['switch']
                    self.params[vlan_name]['port'] = device_info['port']
                    self.params[vlan_name]['iface'] = iface
                    self.nodes_seen.append(' '.join([device_info['switch'], str(device_info['port'])]))
                    break
        self.logger.debug("[%s] vland params: %s", device['hostname'], self.params)
        super(VlandProtocol, self).configure(device, job)
        return True

    def deploy_vlans(self):
        """
        Calls vland to create a vlan. Passes -1 to get the next available vlan tag
        Always passes False to is_base_vlan
        friendly_name is the name specified by the test writer and is not sent to vland.
        self.names maps the friendly names to unique names for the VLANs, usable on the switches themselves.
        Some switches have limits on the allowed characters and length of the name, so this
        string is controlled by the protocol and differs from the friendly name supplied by the
        test writer. Each VLAN also has an ID which is used to identify the VLAN to vland, this
        ID is stored in self.vlans for each friendly_name for use with vland.
        The vlan tag is also stored but not used by the protocol itself.
        """
        # FIXME implement a fake daemon to test the calls
        # create vlans by iterating and appending to self.base_group for the vlan name
        # run_admin_command --create_vlan test30 -1 false
        if self.sub_id != 0:
            for friendly_name, _ in self.names.items():
                self.vlans[friendly_name], tag = self._wait_on_create(friendly_name)
                self.logger.debug("vlan name: %s vlan tag: %s", self.vlans[friendly_name], tag)
        else:
            for friendly_name, _ in self.names.items():
                self.logger.info("Deploying vlan %s : %s", friendly_name, self.names[friendly_name])
                try:
                    self.vlans[friendly_name], tag = self._create_vlan(friendly_name)
                except RuntimeError as exc:
                    raise JobError("Deploy vlans failed for %s: %s" % (friendly_name, exc))
                self.logger.debug("vlan name: %s vlan tag: %s", self.vlans[friendly_name], tag)
                if not tag:  # error state from create_vlan
                    raise JobError("Unable to create vlan %s", friendly_name)
                self._declare_created(friendly_name, tag)
        for friendly_name, _ in self.names.items():
            params = self.params[friendly_name]
            switch_id = self._lookup_switch_id(params['switch'])
            port_id = self._lookup_port_id(switch_id, params['port'])
            self.logger.info("Setting switch %s port %s to vlan %s on %s",
                             params['switch'], params['port'], friendly_name, params['iface'])
            self._set_port_onto_vlan(self.vlans[friendly_name], port_id)
            self.ports.append(port_id)

    def __call__(self, args):
        try:
            return self._api_select(args)
        except (ValueError, TypeError) as exc:
            msg = "Invalid call to %s %s" % (self.name, exc)
            self.logger.exception(msg)
            raise JobError(msg)

    def _api_select(self, data):
        if not data:
            raise TestError("Protocol called without any data")
        if 'request' not in data:
            raise JobError("Bad API call over protocol - missing request")
        if data['request'] == 'deploy_vlans':
            self.deploy_vlans()
        else:
            raise JobError("Unrecognised API call in request.")
        return None

    def check_timeout(self, duration, data):
        if not data:
            raise TestError("Protocol called without any data")
        if 'request' not in data:
            raise JobError("Bad API call over protocol - missing request")
        if data['request'] == 'deploy_vlans':
            if duration < VLAND_DEPLOY_TIMEOUT:
                raise JobError("Timeout of %s is insufficient for deploy_vlans", duration)
            self.logger.info("Setting vland base timeout to %s seconds", duration)
            self.poll_timeout.duration = duration
            return True
        return False

    def finalise_protocol(self, device=None):
        # restore any ports to base_vlan
        for port_id in self.ports:
            self.logger.info("Finalizing port %s", port_id)
            self._restore_port(port_id)
        # then delete any vlans
        for friendly_name, vlan_id in self.vlans.items():
            self.logger.info("Finalizing vlan %s", vlan_id)
            self._delete_vlan(friendly_name, vlan_id)
