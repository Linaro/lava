# Copyright (C) 2017 The Linux Foundation
#
# Author: Jan-Simon Moeller <jsmoeller@linuxfoundation.org>
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


import pexpect
import logging
from lava_dispatcher.connection import Protocol
from lava_common.timeout import Timeout
from lava_common.exceptions import (
    JobError,
    TestError,
)
from lava_dispatcher.shell import ShellCommand
from lava_common.constants import XNBD_SYSTEM_TIMEOUT
from lava_dispatcher.utils.network import dispatcher_ip
from lava_dispatcher.utils.network import get_free_port


class XnbdProtocol(Protocol):
    """
    Xnbd protocol (xnbd-server teardown)
    """
    name = "lava-xnbd"

    def __init__(self, parameters, job_id):
        super().__init__(parameters, job_id)
        # timeout in utils.constants, default 10000
        self.system_timeout = Timeout('system', XNBD_SYSTEM_TIMEOUT)
        self.logger = logging.getLogger('dispatcher')
        self.parameters = parameters
        self.port = None
        self.ports = []

    @classmethod
    def accepts(cls, parameters):
        if 'protocols' not in parameters:
            return False
        if 'lava-xnbd' not in parameters['protocols']:
            return False
        return True

    def collate(self, reply, params):
        params.update(reply)

    def set_up(self):
        """
        Called from the job at the start of the run step.
        """

        if 'port' not in self.parameters['protocols']['lava-xnbd']:
            self.errors = ('No port set in parameters for lava-xnbd protocol!\nE.g.:\n protocols:\n  lava-xnbd:\n    port: auto \n')

    def __call__(self, *args, **kwargs):
        action = kwargs.get('action', None)
        self.logger.debug("[%s] Checking protocol data for %s", action.name, self.name)
        try:
            return self._api_select(args, action=action)
        except (ValueError, TypeError) as exc:
            raise JobError("Invalid call to %s %s" % (self.name, exc))

    def _api_select(self, data, action=None):
        if not data:
            raise TestError("Protocol called without any data")
        for item in data:
            if 'request' not in item:
                raise JobError("Bad API call over protocol - missing request")
            if 'set_port' in item['request']:
                return self.set_port(action=action)
            else:
                raise JobError("Unrecognised API call in request.")
        return None

    def set_port(self, action):
        msg = {
            'data': {
                'nbd_server_port': 10809
            }
        }
        nbd_port = self.parameters['protocols']['lava-xnbd']['port']
        if nbd_port == 'auto':
            self.logger.debug("Get a port from pool")
            nbd_port = get_free_port(self.parameters['dispatcher'])
        self.ports.append(nbd_port)
        msg['data']['nbd_server_port'] = nbd_port
        action.set_namespace_data('nbd-deploy', label='nbd', key='nbd_server_port', value=nbd_port, parameters=action.parameters)
        nbd_ip = dispatcher_ip(self.parameters['dispatcher'])
        action.set_namespace_data('nbd-deploy', label='nbd', key='nbd_server_ip', value=nbd_ip, parameters=action.parameters)
        self.logger.debug("Set_port %d", nbd_port)
        return msg['data']

    def finalise_protocol(self, device=None):
        """Called by Finalize action to power down and clean up the assigned
        device.
        """
        # shutdown xnbd for the given device/job based in the port-number used
        try:
            self.logger.debug("%s cleanup", self.name)
            for port in self.ports:
                self.logger.debug("clean NBD port %s", port)
                nbd_cmd = "pkill -f xnbd-server.*%s" % (port)
                shell = ShellCommand("%s\n" % nbd_cmd, self.system_timeout,
                                     logger=self.logger)
                shell.expect(pexpect.EOF)
        except Exception as e:
            self.logger.debug(str(e))
            self.logger.debug("xnbd-finalize-protocol failed, but continuing anyway.")
