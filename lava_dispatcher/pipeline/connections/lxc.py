# Copyright (C) 2016 Linaro Limited
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

import os
import signal
from time import sleep
from lava_dispatcher.pipeline.utils.shell import infrastructure_error
from lava_dispatcher.pipeline.action import (
    Action,
    JobError,
)
from lava_dispatcher.pipeline.shell import ShellCommand, ShellSession
from lava_dispatcher.pipeline.utils.constants import USB_SHOW_UP_TIMEOUT

# pylint: disable=too-many-public-methods


class ConnectLxc(Action):
    """
    Class to make a lxc shell connection to the container.
    """
    def __init__(self):
        super(ConnectLxc, self).__init__()
        self.name = "connect-lxc"
        self.summary = "run connection command"
        self.description = "connect to the lxc container"
        self.session_class = ShellSession
        self.shell_class = ShellCommand

    def validate(self):
        if 'lxc' not in self.job.device['actions']['boot']['methods']:
            return
        super(ConnectLxc, self).validate()
        self.errors = infrastructure_error('lxc-attach')
        if 'prompts' not in self.parameters:
            self.errors = "Unable to identify test image prompts from parameters."

    def run(self, connection, args=None):
        lxc_name = self.get_common_data('lxc', 'name')
        if not lxc_name:
            self.logger.debug("No LXC device requested")
            return connection

        cmd = "lxc-attach -n {0}".format(lxc_name)
        self.logger.info("%s Connecting to device using '%s'", self.name, cmd)
        signal.alarm(0)  # clear the timeouts used without connections.
        # ShellCommand executes the connection command
        shell = self.shell_class("%s\n" % cmd, self.timeout,
                                 logger=self.logger)
        if shell.exitstatus:
            raise JobError("%s command exited %d: %s" % (cmd,
                                                         shell.exitstatus,
                                                         shell.readlines()))
        # ShellSession monitors the pexpect
        connection = self.session_class(self.job, shell)
        connection.connected = True
        connection = super(ConnectLxc, self).run(connection, args)
        connection.prompt_str = self.parameters['prompts']
        self.data['boot-result'] = 'failed' if self.errors else 'success'
        return connection
