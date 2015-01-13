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

from lava_dispatcher.pipeline.action import (
    Boot,
    Pipeline,
    Action,
    RetryAction,
    JobError,
    Timeout
)
from lava_dispatcher.pipeline.actions.boot import BootAction
from lava_dispatcher.pipeline.shell import ExpectShellSession, ShellCommand, ShellSession
from lava_dispatcher.pipeline.utils.constants import AUTOLOGIN_DEFAULT_TIMEOUT
from lava_dispatcher.pipeline.utils.shell import which
from lava_dispatcher.pipeline.actions.boot import AutoLoginAction


class BootKVM(Boot):
    """
    The Boot method prepares the command to run on the dispatcher but this
    command needs to start a new connection and then allow AutoLogin, if
    enabled, and then expect a shell session which can be handed over to the
    test method. self._run_command is a blocking call, so Boot needs to use
    a direct spawn call via ShellCommand (which wraps pexpect.spawn) then
    hand this pexpect wrapper to subsequent actions as a shell connection.
    """

    def __init__(self, parent, parameters):
        super(BootKVM, self).__init__(parent)
        self.action = BootQEMUImageAction()
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if 'method' not in parameters:
            return False
        if parameters['method'] != 'qemu':
            return False
        if device.parameters['device_type'] == 'kvm':  # FIXME: device_type should likely be qemu - see also deploy
            return True
        return False


class BootQEMUImageAction(BootAction):

    def __init__(self):
        super(BootQEMUImageAction, self).__init__()
        self.name = 'boot_image_retry'
        self.description = "boot image with retry"
        self.summary = "boot with retry"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(BootQemuRetry())
        # Add AutoLoginAction unconditionnally as this action does nothing if
        # the configuration does not contain 'auto_login'
        auto_login = AutoLoginAction()
        auto_login.timeout = Timeout(self.name, AUTOLOGIN_DEFAULT_TIMEOUT)
        self.internal_pipeline.add_action(auto_login)
        self.internal_pipeline.add_action(ExpectShellSession())


class BootQemuRetry(RetryAction):

    def __init__(self):
        super(BootQemuRetry, self).__init__()
        self.name = 'boot_qemu_image'
        self.description = "boot image using QEMU command line"
        self.summary = "boot QEMU image"
        self.overrides = None

    def validate(self):
        super(BootQemuRetry, self).validate()
        try:
            # FIXME: need a schema and do this inside the NewDevice with a QemuDevice class? (just for parsing)
            params = self.job.device.parameters['actions']['boot']
            arch = self.job.device.parameters['architecture']
            qemu_binary = which(params['command'][arch]['qemu_binary'])
            self.overrides = params['overrides']  # FIXME: resolve how to allow overrides in the schema
            command = [
                qemu_binary,
                "-machine",
                params['parameters']['machine'],
                # "-hda",
                # self.data['download_action']['file'],
            ]
            # these options are lists
            for net_opt in params['parameters']['net']:
                command.extend(["-net", net_opt])
            for opt in params['parameters']['qemu_options']:
                command.extend([opt])
            self.set_common_data('qemu-command', 'command', command)
        except (KeyError, TypeError):
            self.errors = "Invalid parameters"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(CallQemuAction())


class CallQemuAction(Action):

    def __init__(self):
        super(CallQemuAction, self).__init__()
        self.name = "execute-qemu"
        self.description = "call qemu to boot the image"
        self.summary = "execute qemu to boot the image"

    def run(self, connection, args=None):
        """
        CommandRunner expects a pexpect.spawn connection which is the return value
        of target.device.power_on executed by boot in the old dispatcher.

        In the new pipeline, the pexpect.spawn is a ShellCommand and the
        connection is a ShellSession. CommandRunner inside the ShellSession
        turns the ShellCommand into a runner which the ShellSession uses via ShellSession.run()
        to run commands issued *after* the device has booted.
        pexpect.spawn is one of the raw_connection objects for a Connection class.
        """
        if 'download_action' not in self.data:
            raise RuntimeError("Value for download_action is missing from %s" % self.name)
        if 'image' not in self.data['download_action']:
            raise RuntimeError("No image file setting from the download_action")
        command = self.get_common_data('qemu-command', 'command')
        command.extend(["-hda", self.data['download_action']['image']['file']])
        self.logger.debug("Boot command: %s" % ' '.join(command))

        # initialise the first Connection object, a command line shell into the running QEMU.
        shell = ShellCommand(' '.join(command), self.timeout)
        if shell.exitstatus:
            raise JobError("%s command exited %d: %s" % (command, shell.exitstatus, shell.readlines()))
        self.logger.debug("started a shell command")

        shell_connection = ShellSession(self.job, shell)
        shell_connection.prompt_str = self.job.device.parameters['test_image_prompts']

        # FIXME: tests with multiple boots need to be handled too.
        self.data['boot-result'] = 'failed' if self.errors else 'success'
        return shell_connection
