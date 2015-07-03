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

# pylint: disable=too-many-return-statements

from lava_dispatcher.pipeline.action import Pipeline, Action
from lava_dispatcher.pipeline.logical import Boot, RetryAction
from lava_dispatcher.pipeline.actions.boot import AutoLoginAction
from lava_dispatcher.pipeline.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.pipeline.utils.shell import infrastructure_error
from lava_dispatcher.pipeline.shell import ExpectShellSession
from lava_dispatcher.pipeline.connections.ssh import ConnectSsh


class SshLogin(Boot):
    """
    Ssh boot strategy is a login process, without actually booting a kernel
    but still needs AutoLoginAction.
    """
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
        self.internal_pipeline.add_action(ConnectSsh())
        self.internal_pipeline.add_action(AutoLoginAction())
        self.internal_pipeline.add_action(ExpectShellSession())
        self.internal_pipeline.add_action(ExportDeviceEnvironment())
        self.internal_pipeline.add_action(ScpOverlayUnpack())


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
        cmd = "tar --warning no-timestamp -C / -xaf /%s" % filename
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
