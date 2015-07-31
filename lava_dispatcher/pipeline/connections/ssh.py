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


import os
import signal
from lava_dispatcher.pipeline.action import JobError
from lava_dispatcher.pipeline.utils.filesystem import check_ssh_identity_file
from lava_dispatcher.pipeline.utils.shell import infrastructure_error
from lava_dispatcher.pipeline.action import Action
from lava_dispatcher.pipeline.shell import ShellCommand, ShellSession

# pylint: disable=too-many-public-methods


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
        self.sendline('logout')
        self.connected = False


class ConnectSsh(Action):
    """
    Initiate an SSH connection from the dispatcher to a device.
    Connections from test images can be done in test definitions.
    This class reads the destination data directly from the device configuration.
    For SSH connections based on protocols and dynamic data from a test image,
    use ConnectDynamicSsh.
    This is a Boot action with Retry support.

    Note the syntax requirements of methods:
    methods:
    -  image
    -  ssh:

    This allows ssh to be a dict, image to be a string (or a dict) and methods to be a list.
    """

    def __init__(self):
        super(ConnectSsh, self).__init__()
        self.name = "primary-ssh"
        self.summary = "make an ssh connection to a known device"
        self.description = "login to a known device using ssh"
        self.command = None
        self.host = None
        self.ssh_port = ["-p", "22"]
        self.scp_port = ["-P", "22"]
        self.identity_file = None
        self.ssh_user = 'root'

    def _check_params(self):
        # the deployment strategy ensures that this key exists
        # use a different class if the destination is set using common_data, e.g. protocols
        if not any('ssh' in data for data in self.job.device['actions']['deploy']['methods']):
            self.errors = "Invalid device configuration - no suitable deploy method for ssh"
            return
        params = self.job.device['actions']['deploy']['methods']
        check = check_ssh_identity_file(params)
        if check[0]:
            self.errors = check[0]
        elif check[1]:
            self.identity_file = check[1]
        if 'ssh' not in params:
            self.errors = "Empty ssh parameter list in device configuration %s" % params
            return
        if any([option for option in params['ssh']['options'] if type(option) != str]):
            msg = [(option, type(option)) for option in params['ssh']['options'] if type(option) != str]
            self.errors = "[%s] Invalid device configuration: all options must be only strings: %s" % (self.name, msg)
            return
        if 'port' in params['ssh']:
            self.ssh_port = ["-p", "%s" % str(params['ssh']['port'])]
            self.scp_port = ["-P", "%s" % str(params['ssh']['port'])]
        if 'options' not in params['ssh']:
            self.errors = "Missing ssh options in device configuration"
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
        if self.valid:
            self.command = ['ssh']
            self.command.extend(params['options'])

    def run(self, connection, args=None):
        if connection:
            self.logger.debug("Already connected")
            return connection
        signal.alarm(0)  # clear the timeouts used without connections.
        # ShellCommand executes the connection command

        params = self._check_params()
        if self.valid:
            self.command = ['ssh']
            self.command.extend(params['options'])
        command = self.command[:]  # local copy for idempotency
        command.extend(['-i', self.identity_file])

        if self.host:
            command.append("%s@%s" % (self.ssh_user, self.host))
        else:
            # get from the protocol
            pass
        command_str = " ".join(str(item) for item in command)
        # use device data for destination
        self.logger.info("%s Connecting to device %s using '%s'", self.name, self.host, command_str)
        shell = ShellCommand("%s\n" % command_str, self.timeout)
        if shell.exitstatus:
            raise JobError("%s command exited %d: %s" % (
                self.command, shell.exitstatus, shell.readlines()))
        # SshSession monitors the pexpect
        connection = SShSession(self.job, shell)
        connection = super(ConnectSsh, self).run(connection, args)
        connection.prompt_str = self.job.device['test_image_prompts']
        connection.connected = True
        self.wait(connection)
        self.data["boot-result"] = 'success'
        return connection


class Scp(ConnectSsh):
    """
    Use the SSH connection options to copy files over SSH
    One action per scp operation, just as with download action
    Needs the reference into the common data for each file to copy
    This is a Deploy action. lava-start is managed by the protocol,
    when this action starts, the device is in the "receiving" state.
    """
    def __init__(self, key):
        super(Scp, self).__init__()
        self.name = "scp-deploy"  # FIXME: confusing name as this is in the connections folder, not actions/deploy.
        self.summary = "scp over the ssh connection"
        self.description = "copy a file to a known device using scp"
        self.key = key
        self.scp = []

    def validate(self):
        super(Scp, self).validate()
        params = self._check_params()
        self.errors = infrastructure_error('scp')
        if self.valid:
            self.scp.append('scp')
            self.scp.extend(params['options'])

    def run(self, connection, args=None):
        path = self.get_common_data(self.name, self.key)
        if not path:
            self.errors = "%s: could not find details of '%s'" % (self.name, self.key)
            self.logger.error("%s: could not find details of '%s'" % (self.name, self.key))
            return connection
        destination = "%s-%s" % (self.job.job_id, os.path.basename(path))
        command = self.scp[:]  # local copy
        command.extend(['-i', self.identity_file])
        # add the local file as source
        command.append(path)
        # add the remote as destination, with :/ top level directory
        command.append("%s:/%s" % (self.host, destination))
        command_str = " ".join(str(item) for item in command)
        self.logger.info("Copying %s using %s" % (self.key, command_str))
        self.run_command(command)
        connection = super(Scp, self).run(connection, args)
        self.wait(connection)
        self.set_common_data('scp-overlay-unpack', 'overlay', destination)
        self.wait(connection)
        return connection


class ConnectDynamicSsh(ConnectSsh):
    """
    Adaptation to read the destination from common data / protocol
    Connect from the dispatcher to a dynamically provisioned ssh server
    Returns a new Connection.
    """
    def __init__(self):
        super(ConnectDynamicSsh, self).__init__()
        self.name = "ssh-connect"
        self.summary = "connect to a test image using ssh"
        self.description = "login to a test image using a declared IP address"

    def run(self, connection, args=None):
        if connection:
            self.logger.debug("Already connected")
            return connection
        # FIXME
