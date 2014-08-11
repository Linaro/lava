# Copyright (C) 2014 Linaro Limited
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
import sys
from lava_dispatcher.pipeline.action import (
    Boot,
    Pipeline,
    InfrastructureError,
    Timeout,
    JobError
)
from lava_dispatcher.pipeline.actions.boot import BootAction, AutoLoginAction
from lava_dispatcher.pipeline.shell import ExpectShellSession, ShellCommand, ShellSession


class BootKVM(Boot):
    """
    The Boot method prepares the command to run on the dispatcher but this
    command needs to start a new connection and then allow AutoLogin, if
    enabled, and then expect a shell session which can be handed over to the
    test method. self._run_command is a blocking call, so Boot needs to use
    a direct spawn call via ShellCommand (which wraps pexpect.spawn) then
    hand this pexpect wrapper to subsequent actions as a shell connection.
    """

    def __init__(self, parent):
        super(BootKVM, self).__init__(parent)
        self.action = BootQEMUImageAction()
        self.action.job = self.job
        parent.add_action(self.action)

        internal_pipeline = Pipeline(parent=self.action, job=self.job)
        if 'auto_login' in self.action.parameters:
            internal_pipeline.add_action(AutoLoginAction())
        internal_pipeline.add_action(ExpectShellSession())

    @classmethod
    def accepts(cls, device, parameters):
        # FIXME: needs to do more work with job parameters before accepting
        if hasattr(device, 'config'):
            if device.config.device_type == 'kvm':  # FIXME: teach base unit tests to use new style Device objects
                return True
        else:
            if device.parameters['device_type'] == 'kvm':  # FIXME: device_type should likely be qemu - see also deploy
                return True
        return False


class BootQEMUImageAction(BootAction):

    def __init__(self):
        super(BootQEMUImageAction, self).__init__()
        self.name = 'boot_qemu_image'
        self.description = "boot image using QEMU command line"
        self.summary = "boot QEMU image"
        self.overrides = None
        self.command = []
        self.timeout = Timeout(self.name)  # FIXME: decide on a duration for the boot QEMU Image timeout

    # FIXME: move into a new utils module?
    def _find(self, path, match=os.path.isfile):
        """
        Simple replacement for the `which` command found on
        Debian based systems.
        """
        for dirname in sys.path:
            candidate = os.path.join(dirname, path)
            if match(candidate):
                return candidate
        raise InfrastructureError("Cannot find file %s" % path)

    def validate(self):
        if not hasattr(self.job.device, 'config'):  # FIXME: new devices only
            try:
                # FIXME: need a schema and do this inside the NewDevice with a QemuDevice class? (just for parsing)
                params = self.job.device.parameters['actions']['boot']
                arch = self.job.device.parameters['architecture']
                qemu_binary = self._find(params['command'][arch]['qemu_binary'])
                self.overrides = params['overrides']  # FIXME: resolve how to allow overrides in the schema
                self.command = [
                    qemu_binary,
                    "-machine",
                    params['parameters']['machine'],
                    "-hda",
                    self.data['download_action']['file'],
                ]
                # these options are lists
                for net_opt in params['parameters']['net']:
                    self.command.extend(["-net", net_opt])
                for opt in params['parameters']['qemu_options']:
                    self.command.extend([opt])
            except (KeyError, TypeError) as exc:
                raise RuntimeError(exc)

    def run(self, connection, args=None):
        self._log("Boot command: %s" % ' '.join(self.command))
        # initialise the first Connection object, a command line shell into the running QEMU.
        # ShellCommand wraps pexpect.spawn.
        shell = ShellCommand(' '.join(self.command), self.timeout)
        if shell.exitstatus:
            raise JobError("%s command exited %d: %s" % (self.command, shell.exitstatus, shell.readlines()))
        self._log("started a shell command")
        # CommandRunner expects a pexpect.spawn connection which is the return value
        # of target.device.power_on executed by boot in the old dispatcher.
        #
        # In the new pipeline, the pexpect.spawn is a ShellCommand and the
        # connection is a ShellSession. CommandRunner inside the ShellSession
        # turns the ShellCommand into a runner which the ShellSession uses via ShellSession.run()
        # to run commands issued *after* the device has booted.
        # pexpect.spawn is one of the raw_connection objects for a Connection class.
        shell_connection = ShellSession(self.job.device, shell)
        self.pipeline.run_actions(shell_connection)
        return shell_connection
