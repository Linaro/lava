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
        self.identity_file = None

    def _check_params(self):
        # the deployment strategy ensures that this key exists
        # use a different class if the destination is set using common_data, e.g. protocols
        if not any('ssh' in data for data in self.job.device['actions']['deploy']['methods']):
            self.errors = "Invalid device configuration - no suitable deploy method for ssh"
            return
        params = self.job.device['actions']['deploy']['methods']
        if 'ssh' not in params:
            self.errors = "Empty ssh parameter list in device configuration %s" % params
            return
        if 'options' not in params['ssh']:
            self.errors = "Missing ssh options in device configuration"
        if 'identity_file' not in params['ssh']:
            self.errors = "Missing entry for SSH private key"
        if os.path.isabs(params['ssh']['identity_file']):
            self.identity_file = params['ssh']['identity_file']
        else:
            self.identity_file = os.path.realpath(os.path.join(__file__, '../../../', params['ssh']['identity_file']))
        if not os.path.exists(self.identity_file):
            self.errors = "Cannot find SSH private key %s" % self.identity_file
        if 'host' in params['ssh'] and params['ssh']['host']:
            # get the value from the protocol later.
            self.host = params['ssh']['host']
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
            command.append(str(self.host))
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
        self.name = "scp-deploy"
        self.summary = "scp over the ssh connection"
        self.description = "copy a file to a known device using scp"
        self.key = key

    def validate(self):
        super(Scp, self).validate()
        params = self._check_params()
        self.errors = infrastructure_error('scp')
        if self.valid:
            # FIXME: this causes overwriting issues
            self.command = ['scp']
            self.command.extend(params['options'])

    def run(self, connection, args=None):
        path = self.get_common_data(self.name, self.key)
        if not path:
            self.errors = "%s: could not find details of '%s'" % (self.name, self.key)
            self.logger.error("%s: could not find details of '%s'" % (self.name, self.key))
            return connection
        # FIXME: being overwritten, why?
        command = self.command[:]  # local copy
        command.extend(['-i', self.identity_file])
        # add the local file as source
        command.append(path)
        # add the remote as destination, with :/ top level directory
        command.append("%s:/" % self.host)
        command_str = " ".join(str(item) for item in command)
        self.logger.info("Copying %s using %s" % (self.key, command_str))
        self.run_command(command)
        connection = super(Scp, self).run(connection, args)
        self.wait(connection)
        connection.sendline('tar -C / -xzf /%s\n' % os.path.basename(path))
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
