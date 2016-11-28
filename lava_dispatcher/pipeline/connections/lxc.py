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

        if 'device_path' in list(self.job.device.keys()):
            device_path = self.job.device['device_path']
            if not isinstance(device_path, list):
                raise JobError("device_path should be a list")

            if device_path:
                # Wait USB_SHOW_UP_TIMEOUT seconds for usb device to show up
                self.logger.info("[%s] Wait %d seconds for usb device to show up",
                                 self.name, USB_SHOW_UP_TIMEOUT)
                sleep(USB_SHOW_UP_TIMEOUT)

                for path in device_path:
                    path = os.path.realpath(path)
                    if os.path.isdir(path):
                        devices = os.listdir(path)
                    else:
                        devices = [path]

                    for device in devices:
                        device = os.path.join(path, device)
                        if os.path.exists(device):
                            lxc_cmd = ['lxc-device', '-n', lxc_name, 'add', device]
                            log = self.run_command(lxc_cmd)
                            self.logger.debug(log)
                            self.logger.debug("%s: devices added from %s",
                                              lxc_name, path)
                        else:
                            self.logger.info("%s: skipped adding %s device",
                                             lxc_name, device)
            else:
                self.logger.warning("device_path is None")
        else:
            self.logger.debug("No device path defined for this device.")

        namespace = self.parameters.get('namespace', None)
        if namespace:
            connection = self.get_common_data(namespace, 'connection',
                                              deepcopy=False)
            if connection:
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
        if namespace:
            self.set_common_data(namespace, 'connection', connection)
        return connection
