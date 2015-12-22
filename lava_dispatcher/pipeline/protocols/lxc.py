# Copyright (C) 2015 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
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
    JobError,
)
from lava_dispatcher.pipeline.shell import ShellCommand
from lava_dispatcher.pipeline.utils.constants import LAVA_LXC_TIMEOUT


class LxcProtocol(Protocol):
    """
    Lxc API protocol.
    """
    name = "lava-lxc"

    def __init__(self, parameters):
        super(LxcProtocol, self).__init__(parameters)
        self.system_timeout = Timeout('system', LAVA_LXC_TIMEOUT)
        self.lxc_name = parameters['protocols'][self.name]['name']
        self.lxc_dist = parameters['protocols'][self.name]['distribution']
        self.lxc_release = parameters['protocols'][self.name]['release']
        self.lxc_arch = parameters['protocols'][self.name]['arch']
        self.logger = logging.getLogger('dispatcher')

    @classmethod
    def accepts(cls, parameters):
        if 'protocols' not in parameters:
            return False
        if 'lava-lxc' not in parameters['protocols']:
            return False
        if 'name' not in parameters['protocols']['lava-lxc']:
            return False
        if 'distribution' not in parameters['protocols']['lava-lxc']:
            return False
        if 'release' not in parameters['protocols']['lava-lxc']:
            return False
        if 'arch' not in parameters['protocols']['lava-lxc']:
            return False
        return True

    def set_up(self):
        """
        Called from the job at the start of the run step.
        """
        pass

    def finalise_protocol(self):
        # ShellCommand executes the destroy command
        cmd = "lxc-destroy -n {0} -f".format(self.lxc_name)
        self.logger.debug("%s protocol: executing '%s'", self.name, cmd)
        shell = ShellCommand("%s\n" % cmd, self.system_timeout,
                             logger=self.logger)
        # execute the command.
        shell.expect(pexpect.EOF)
        if shell.exitstatus:
            raise JobError("%s command exited %d: %s" % (cmd, shell.exitstatus,
                                                         shell.readlines()))
        self.logger.debug("%s protocol finalised." % self.name)
