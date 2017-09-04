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
from lava_dispatcher.pipeline.connection import Protocol
from lava_dispatcher.pipeline.action import (
    Timeout,
)
from lava_dispatcher.pipeline.utils.shell import infrastructure_error
from lava_dispatcher.pipeline.shell import ShellCommand
from lava_dispatcher.pipeline.utils.constants import XNBD_SYSTEM_TIMEOUT


class XnbdProtocol(Protocol):
    """
    Xnbd protocol (xnbd-server teardown)
    """
    name = "lava-xnbd"

    def __init__(self, parameters, job_id):
        super(XnbdProtocol, self).__init__(parameters, job_id)
        # timeout in utils.constants, default 10000
        self.system_timeout = Timeout('system', XNBD_SYSTEM_TIMEOUT)
        self.logger = logging.getLogger('dispatcher')
        self.parameters = parameters
        self.port = None

    @classmethod
    def accepts(cls, parameters):
        if 'protocols' not in parameters:
            return False
        if 'lava-xnbd' not in parameters['protocols']:
            return False
        return True

    def set_up(self):
        """
        Called from the job at the start of the run step.
        """

        if 'port' not in self.parameters['protocols']['lava-xnbd']:
            self.errors = ('No port set in parameters for lava-xnbd protocol!\nE.g.:\n protocols:\n  lava-xnbd:\n    port: auto \n')

    def finalise_protocol(self, device=None):
        """Called by Finalize action to power down and clean up the assigned
        device.
        """
        # shutdown xnbd for the given device/job based in the port-number used
        try:
            self.logger.debug("%s cleanup", self.name)
            self.port = self.parameters['protocols']['lava-xnbd']['port']
            nbd_cmd = "pkill -f xnbd-server.*%s" % (self.port)
            shell = ShellCommand("%s\n" % nbd_cmd, self.system_timeout,
                                 logger=self.logger)
            shell.expect(pexpect.EOF)
        except Exception as e:
            self.logger.debug(str(e))
            self.logger.debug("xnbd-finalize-protocol failed, but continuing anyway.")
