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

# pylint: disable=too-many-return-statements,too-many-instance-attributes

import os
import yaml
from lava_dispatcher.pipeline.action import Pipeline, Action
from lava_dispatcher.pipeline.logical import Boot, RetryAction
from lava_dispatcher.pipeline.actions.boot import AutoLoginAction
from lava_dispatcher.pipeline.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.pipeline.utils.shell import infrastructure_error
from lava_dispatcher.pipeline.shell import ExpectShellSession
from lava_dispatcher.pipeline.connections.ssh import ConnectSsh
from lava_dispatcher.pipeline.protocols.multinode import MultinodeProtocol


class SshLogin(Boot):
    """
    Ssh boot strategy is a login process, without actually booting a kernel
    but still needs AutoLoginAction.
    """

    compatibility = 1

    def __init__(self, parent, parameters):
        super(SshLogin, self).__init__(parent)
        self.action = SshAction()
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if 'actions' not in device or 'boot' not in device['actions']:
            return False
        if 'methods' not in device['actions']['boot']:
            return False
        if 'ssh' not in device['actions']['boot']['methods']:
            return False
        # It is an error to have multiple keys - each method is a dict with a single key
        params = device['actions']['boot']['methods']
        if not params:
            return False
        if not any('ssh' in data for data in params):
            return False
        if 'ssh' not in parameters['method']:
            return False
        return True


class SshAction(RetryAction):
    """
    Simple action to wrap AutoLoginAction and ExpectShellSession
    """
    def __init__(self):
        super(SshAction, self).__init__()
        self.name = "login-ssh"
        self.summary = "login over ssh"
        self.description = "connect over ssh and ensure a shell is found"
        self.section = 'boot'

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        scp = Scp('overlay')
        self.internal_pipeline.add_action(scp)
        self.internal_pipeline.add_action(PrepareSsh())
        self.internal_pipeline.add_action(ConnectSsh())
        self.internal_pipeline.add_action(AutoLoginAction())
        self.internal_pipeline.add_action(ExpectShellSession())
        self.internal_pipeline.add_action(ExportDeviceEnvironment())
        self.internal_pipeline.add_action(ScpOverlayUnpack())


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
        self.scp = []

    def validate(self):
        super(Scp, self).validate()
        params = self._check_params()
        self.errors = infrastructure_error('scp')
        if 'ssh' not in self.job.device['actions']['deploy']['methods']:
            self.errors = "Unable to use %s without ssh deployment" % self.name
        if 'ssh' not in self.job.device['actions']['boot']['methods']:
            self.errors = "Unable to use %s without ssh boot" % self.name
        if self.get_common_data("prepare-scp-overlay", self.key):
            self.primary = False
        elif 'host' not in self.job.device['actions']['deploy']['methods']['ssh']:
            self.errors = "Invalid device or job configuration, missing host."
        if not self.primary and len(
                self.get_common_data("prepare-scp-overlay", self.key)) != 1:
            self.errors = "Invalid number of host_keys"
        if 'port' in self.job.device['actions']['deploy']['methods']['ssh']:
            port = str(self.job.device['actions']['deploy']['methods']['ssh']['port'])
            if not port.isdigit():
                self.errors = "Port was set but was not a digit"
        if self.valid:
            self.scp.append('scp')
            if 'options' in params:
                self.scp.extend(params['options'])

    def run(self, connection, args=None):
        path = self.get_common_data(self.name, self.key)
        if not path:
            self.errors = "%s: could not find details of '%s'" % (self.name, self.key)
            self.logger.error("%s: could not find details of '%s'", self.name, self.key)
            return connection
        overrides = self.get_common_data("prepare-scp-overlay", self.key)
        if not self.primary:
            self.logger.info("Retrieving common data for prepare-scp-overlay using %s", ','.join(overrides))
            self.host = str(self.get_common_data("prepare-scp-overlay", overrides[0]))
            self.logger.debug("Using common data for host: %s", self.host)
        elif not self.host:
            self.errors = "%s: could not find host for deployment" % self.name
            self.logger.error("%s: could not find host for deployment", self.name)
            return connection
        destination = "%s-%s" % (self.job.job_id, os.path.basename(path))
        command = self.scp[:]  # local copy
        # add the argument for setting the port (-P port)
        command.extend(self.scp_port)

        if self.identity_file:
            command.extend(['-i', self.identity_file])
        # add arguments to ignore host key checking of the host device
        command.extend(['-o', 'UserKnownHostsFile=/dev/null', '-o', 'StrictHostKeyChecking=no'])
        # add the local file as source
        command.append(path)
        command_str = " ".join(str(item) for item in command)
        self.logger.info("Copying %s using %s to %s", self.key, command_str, self.host)
        # add the remote as destination, with :/ top level directory
        command.extend(["%s@%s:/%s" % (self.ssh_user, self.host, destination)])
        self.logger.info(yaml.dump(command))
        self.run_command(command)
        connection = super(Scp, self).run(connection, args)
        self.results = {'success': 'ssh deployment'}
        self.set_common_data('scp-overlay-unpack', 'overlay', destination)
        self.data['boot-result'] = 'failed' if self.errors else 'success'
        return connection


class PrepareSsh(Action):
    """
    Sets the host for the ConnectSsh
    """
    def __init__(self):
        super(PrepareSsh, self).__init__()
        self.name = "prepare-ssh"
        self.summary = "set the host address of the ssh connection"
        self.description = "determine which address to use for primary or secondary connections"
        self.primary = False

    def validate(self):
        if 'parameters' in self.parameters and 'hostID' in self.parameters['parameters']:
            self.set_common_data('ssh-connection', 'host', True)
        else:
            self.set_common_data('ssh-connection', 'host', False)
            self.primary = True

    def run(self, connection, args=None):
        connection = super(PrepareSsh, self).run(connection, args)
        if not self.primary:
            host_data = self.get_common_data(MultinodeProtocol.name, self.parameters['parameters']['hostID'])
            self.set_common_data(
                'ssh-connection', 'host_address',
                host_data[self.parameters['parameters']['host_key']]
            )
        return connection


class ScpOverlayUnpack(Action):

    def __init__(self):
        super(ScpOverlayUnpack, self).__init__()
        self.name = "scp-overlay-unpack"
        self.summary = "unpack the overlay on the remote device"
        self.description = "unpack the overlay over an existing ssh connection"

    def run(self, connection, args=None):
        connection = super(ScpOverlayUnpack, self).run(connection, args)
        if not connection:
            raise RuntimeError("Cannot unpack, no connection available.")
        filename = self.get_common_data(self.name, 'overlay')
        tar_flags = self.get_common_data('scp-overlay', 'tar_flags')
        cmd = "tar %s -C / -xzf /%s" % (tar_flags, filename)
        connection.sendline(cmd)
        self.wait(connection)
        self.data['boot-result'] = 'failed' if self.errors else 'success'
        return connection


class Schroot(Boot):

    def __init__(self, parent, parameters):
        super(Schroot, self).__init__(parent)
        self.action = SchrootAction()
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if 'actions' not in device or 'boot' not in device['actions']:
            return False
        if 'methods' not in device['actions']['boot']:
            return False
        params = device['actions']['boot']['methods']
        if not params:
            return False
        if 'schroot' not in params:
            return False
        if 'method' not in parameters:
            return False
        if 'schroot' not in parameters['method']:
            return False
        return True


class SchrootAction(Action):
    """
    Extends the login to enter an existing schroot as a new schroot session
    using the current connection.
    Does not rely on ssh
    """
    def __init__(self):
        super(SchrootAction, self).__init__()
        self.name = "schroot-login"
        self.summary = "enter specified schroot"
        self.description = "enter schroot using existing connection"
        self.section = 'boot'
        self.schroot = None
        self.command = None

    def validate(self):
        """
        The unit test skips if schroot is not installed, the action marks the
        pipeline as invalid if schroot is not installed.
        """
        if 'schroot' not in self.parameters:
            return
        if 'schroot' not in self.job.device['actions']['boot']['methods']:
            self.errors = "No schroot support in device boot methods"
            return
        self.errors = infrastructure_error('schroot')
        # device parameters are for ssh
        params = self.job.device['actions']['boot']['methods']
        if 'command' not in params['schroot']:
            self.errors = "Missing schroot command in device configuration"
            return
        if 'name' not in params['schroot']:
            self.errors = "Missing schroot name in device configuration"
            return
        self.schroot = params['schroot']['name']
        self.command = params['schroot']['command']

    def run(self, connection, args=None):
        if not connection:
            return connection
        self.logger.info("Entering %s schroot", self.schroot)
        connection.prompt_str = "(%s)" % self.schroot
        connection.sendline(self.command)
        self.wait(connection)
        return connection
