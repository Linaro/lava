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


import signal
from lava_dispatcher.pipeline.action import JobError
from lava_dispatcher.pipeline.utils.filesystem import check_ssh_identity_file
from lava_dispatcher.pipeline.utils.shell import infrastructure_error
from lava_dispatcher.pipeline.action import Action
from lava_dispatcher.pipeline.shell import ShellCommand, ShellSession
from lava_dispatcher.pipeline.utils.constants import DEFAULT_SHELL_PROMPT


# pylint: disable=too-many-public-methods,too-many-instance-attributes


class SShSession(ShellSession):
    """ Extends a ShellSession to include the ability to copy files using scp
    without duplicating the SSH setup, keys etc.
    """
    def __init__(self, job, shell_command):
        super(SShSession, self).__init__(job, shell_command)
        self.name = "SshSession"

    def finalise(self):
        self.disconnect("closing")
        super(SShSession, self).finalise()

    def disconnect(self, reason):
        self.sendline('logout', disconnecting=True)
        self.connected = False


class ConnectSsh(Action):
    """
    Initiate an SSH connection from the dispatcher to a device.
    Connections from test images can be done in test definitions.
    If hostID and host_key are not specified as parameters,
    this class reads the destination data directly from the device configuration.
    This is a Boot action with Retry support.

    Note the syntax requirements of methods:
    methods:
    -  image
    -  ssh:

    This allows ssh to be a dict, image to be a string (or a dict) and methods to be a list.
    """

    def __init__(self):
        super(ConnectSsh, self).__init__()
        self.name = "ssh-connection"
        self.summary = "make an ssh connection to a device"
        self.description = "login to a known device using ssh"
        self.command = None
        self.host = None
        self.ssh_port = ["-p", "22"]
        self.scp_port = ["-P", "22"]
        self.identity_file = None
        self.ssh_user = 'root'
        self.primary = False
        self.scp_prompt = None

    def _check_params(self):
        # the deployment strategy ensures that this key exists
        # use a different class if the destination is set using common_data, e.g. protocols
        if not any('ssh' in data for data in self.job.device['actions']['deploy']['methods']):
            self.errors = "Invalid device configuration - no suitable deploy method for ssh"
            return
        params = self.job.device['actions']['deploy']['methods']
        if 'identity_file' in self.job.device['actions']['deploy']['methods']['ssh']:
            check = check_ssh_identity_file(params)
            if check[0]:
                self.errors = check[0]
            elif check[1]:
                self.identity_file = check[1]
        if 'ssh' not in params:
            self.errors = "Empty ssh parameter list in device configuration %s" % params
            return
        if 'options' in params['ssh']:
            if any([option for option in params['ssh']['options'] if not isinstance(option, str)]):
                msg = [(option, type(option)) for option in params['ssh']['options'] if not isinstance(option, str)]
                self.errors = "[%s] Invalid device configuration: all options must be only strings: %s" % (self.name, msg)
                return
        if 'port' in params['ssh']:
            self.ssh_port = ["-p", "%s" % str(params['ssh']['port'])]
            self.scp_port = ["-P", "%s" % str(params['ssh']['port'])]
        if 'host' in params['ssh'] and params['ssh']['host']:
            # get the value from the protocol later.
            self.host = params['ssh']['host']
        if 'user' in params['ssh'] and params['ssh']['user']:
            self.ssh_user = params['ssh']['user']
        return params['ssh']

    def validate(self):
        super(ConnectSsh, self).validate()
        params = self._check_params()
        self.errors = infrastructure_error('ssh')
        if 'host' in self.job.device['actions']['deploy']['methods']['ssh']:
            self.primary = True
            self.host = self.job.device['actions']['deploy']['methods']['ssh']['host']
        if self.valid:
            self.command = ['ssh']
            if 'options' in params:
                self.command.extend(params['options'])
            # add arguments to ignore host key checking of the host device
            self.command.extend(['-o', 'UserKnownHostsFile=/dev/null', '-o', 'StrictHostKeyChecking=no'])
            if self.identity_file:
                # add optional identity file
                self.command.extend(['-i', self.identity_file])
            self.command.extend(self.ssh_port)

    def run(self, connection, max_end_time, args=None):
        if connection:
            self.logger.debug("Already connected")
            return connection
        # ShellCommand executes the connection command

        params = self._check_params()
        command = self.command[:]  # local copy for idempotency
        overrides = self.get_namespace_data(action='prepare-scp-overlay', label="prepare-scp-overlay", key=self.key)
        host_address = None
        if overrides:
            host_address = str(self.get_namespace_data(
                action='prepare-scp-overlay', label="prepare-scp-overlay", key=overrides[0]))
        if host_address:
            self.logger.info("Using common data to retrieve host_address for secondary connection.")
            command_str = " ".join(str(item) for item in command)
            self.logger.info("%s Connecting to device %s using '%s'", self.name, host_address, command_str)
            command.append("%s@%s" % (self.ssh_user, host_address))
        elif self.host and self.primary:
            self.logger.info("Using device data host_address for primary connection.")
            command_str = " ".join(str(item) for item in command)
            self.logger.info("%s Connecting to device %s using '%s'", self.name, self.host, command_str)
            command.append("%s@%s" % (self.ssh_user, self.host))
        else:
            raise JobError("Unable to identify host address. Primary? %s", self.primary)
        command_str = " ".join(str(item) for item in command)
        shell = ShellCommand("%s\n" % command_str, self.timeout, logger=self.logger)
        if shell.exitstatus:
            raise JobError("%s command exited %d: %s" % (
                self.command, shell.exitstatus, shell.readlines()))
        # SshSession monitors the pexpect
        connection = SShSession(self.job, shell)
        connection = super(ConnectSsh, self).run(connection, max_end_time, args)
        connection.sendline('export PS1="%s"' % DEFAULT_SHELL_PROMPT)
        connection.prompt_str = [DEFAULT_SHELL_PROMPT]
        connection.connected = True
        self.wait(connection)
        res = 'failed' if self.errors else 'success'
        self.set_namespace_data(action='boot', label='shared', key='boot-result', value=res)
        return connection
