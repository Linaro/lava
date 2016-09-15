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
from lava_dispatcher.pipeline.action import (
    Pipeline,
    Action,
    InfrastructureError,
    JobError,
)
from lava_dispatcher.pipeline.logical import Boot, RetryAction
from lava_dispatcher.pipeline.actions.boot import BootAction
from lava_dispatcher.pipeline.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.pipeline.shell import (
    ExpectShellSession,
    ShellCommand,
    ShellSession
)
from lava_dispatcher.pipeline.utils.shell import which
from lava_dispatcher.pipeline.utils.strings import substitute
from lava_dispatcher.pipeline.utils.messages import LinuxKernelMessages
from lava_dispatcher.pipeline.actions.boot import AutoLoginAction


# FIXME: decide if 'media: tmpfs' is necessary or remove from YAML. Only removable needs 'media'
class BootQEMU(Boot):
    """
    The Boot method prepares the command to run on the dispatcher but this
    command needs to start a new connection and then allow AutoLogin, if
    enabled, and then expect a shell session which can be handed over to the
    test method. self.run_command is a blocking call, so Boot needs to use
    a direct spawn call via ShellCommand (which wraps pexpect.spawn) then
    hand this pexpect wrapper to subsequent actions as a shell connection.
    """

    compatibility = 4

    def __init__(self, parent, parameters):
        super(BootQEMU, self).__init__(parent)
        self.action = BootQEMUImageAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if 'method' not in parameters:
            return False
        if parameters['method'] != 'qemu':
            return False
        if device['device_type'] != 'qemu':
            return False
        if parameters['method'] == 'monitor':
            return False
        return True


class BootMonitorQemu(Boot):

    compatibility = 4  # FIXME: change this to 5 and update test cases

    def __init__(self, parent, parameters):
        super(BootMonitorQemu, self).__init__(parent)
        self.action = BootMonitoredQemu()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if 'method' not in parameters:
            return False
        if device['device_type'] != 'qemu':
            return False
        if parameters['method'] != 'monitor':
            return False
        return True


class BootMonitoredQemu(BootAction):

    def __init__(self):
        super(BootMonitoredQemu, self).__init__()
        self.name = 'boot_image_monitor'
        self.description = "boot monitored image with retry"
        self.summary = "boot monitor with retry"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(BootQemuRetry())


class BootQEMUImageAction(BootAction):

    def __init__(self):
        super(BootQEMUImageAction, self).__init__()
        self.name = 'boot_image_retry'
        self.description = "boot image with retry"
        self.summary = "boot with retry"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(BootQemuRetry())
        self.internal_pipeline.add_action(LinuxKernelMessages())
        # Add AutoLoginAction unconditionally as this action does nothing if
        # the configuration does not contain 'auto_login'
        self.internal_pipeline.add_action(AutoLoginAction())
        self.internal_pipeline.add_action(ExpectShellSession())
        self.internal_pipeline.add_action(ExportDeviceEnvironment())


class BootQemuRetry(RetryAction):

    def __init__(self):
        super(BootQemuRetry, self).__init__()
        self.name = 'boot_qemu_image'
        self.description = "boot image using QEMU command line"
        self.summary = "boot QEMU image"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(CallQemuAction())


class MonitorQemuAction(Action):

    def __init__(self):
        super(MonitorQemuAction, self).__init__()
        self.name = "monitor-qemu"
        self.description = "monitor qemu to boot the image"
        self.summary = "monitor qemu to boot the image"
        self.sub_command = []

    def validate(self):
        super(MonitorQemuAction, self).validate()
        try:
            boot = self.job.device['actions']['boot']['methods']['qemu']
            qemu_binary = which(boot['parameters']['command'])
            self.sub_command = [qemu_binary]
            self.sub_command.extend(boot['parameters'].get('options', []))
        except AttributeError as exc:
            raise InfrastructureError(exc)
        except (KeyError, TypeError):
            self.errors = "Invalid parameters for %s" % self.name
        substitutions = {}
        commands = []
        for action in self.data['download_action'].keys():
            if action == 'offset' or action == 'available_loops' or action == 'uefi':
                continue
            image_arg = self.data['download_action'][action].get('image_arg', None)
            action_arg = self.data['download_action'][action].get('file', None)
            if not image_arg or not action_arg:
                self.errors = "Missing image_arg for %s. " % action
                continue
            substitutions["{%s}" % action] = action_arg
            commands.append(image_arg)
        self.sub_command.extend(substitute(commands, substitutions))
        if not self.sub_command:
            self.errors = "No QEMU command to execute"

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
        # initialise the first Connection object, a command line shell into the running QEMU.
        self.logger.info("Boot command: %s", ' '.join(self.sub_command))
        shell = ShellCommand(' '.join(self.sub_command), self.timeout, logger=self.logger)
        if shell.exitstatus:
            raise JobError("%s command exited %d: %s" % (self.sub_command, shell.exitstatus, shell.readlines()))
        self.logger.debug("started a shell command")

        shell_connection = ShellSession(self.job, shell)
        shell_connection = super(MonitorQemuAction, self).run(shell_connection, args)

        # FIXME: the shell needs to wait for something

        # FIXME: tests with multiple boots need to be handled too.
        self.data['boot-result'] = 'failed' if self.errors else 'success'
        # FIXME: from here, go into the new test action.
        return shell_connection


class CallQemuAction(Action):

    def __init__(self):
        super(CallQemuAction, self).__init__()
        self.name = "execute-qemu"
        self.description = "call qemu to boot the image"
        self.summary = "execute qemu to boot the image"
        self.sub_command = []

    def validate(self):
        super(CallQemuAction, self).validate()
        if self.parameters['method'] == 'qemu' and 'prompts' not in self.parameters:
            self.errors = "Unable to identify boot prompts from job definition."
        try:
            boot = self.job.device['actions']['boot']['methods']['qemu']
            if 'parameters' not in boot or 'command' not in boot['parameters']:
                self.errors = "Invalid device configuration - missing parameters"
            elif not boot['parameters']['command']:
                self.errors = "No QEMU binary command found - missing context."
            qemu_binary = which(boot['parameters']['command'])
            self.sub_command = [qemu_binary]
            self.sub_command.extend(boot['parameters'].get('options', []))
            self.sub_command.extend(boot['parameters'].get('extra', []))
        except AttributeError as exc:
            self.errors = "Unable to parse device options: %s %s" % (
                exc, self.job.device['actions']['boot']['methods']['qemu'])
        except (KeyError, TypeError):
            self.errors = "Invalid parameters for %s" % self.name
        substitutions = {}
        commands = []
        for action in self.data['download_action'].keys():
            if action == 'offset' or action == 'available_loops' or action == 'uefi':
                continue
            image_arg = self.data['download_action'][action].get('image_arg', None)
            action_arg = self.data['download_action'][action].get('file', None)
            if not image_arg or not action_arg:
                self.errors = "Missing image_arg for %s. " % action
                continue
            substitutions["{%s}" % action] = action_arg
            commands.append(image_arg)
        self.sub_command.extend(substitute(commands, substitutions))
        if not self.sub_command:
            self.errors = "No QEMU command to execute"
        uefi_dir = self.get_common_data('image', 'uefi_dir')
        if uefi_dir:
            self.sub_command.extend(['-L', uefi_dir, '-monitor', 'none'])

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
        # initialise the first Connection object, a command line shell into the running QEMU.
        guest = self.get_common_data('guest', 'filename')
        if guest:
            self.logger.info("Extending command line for qcow2 test overlay")
            self.sub_command.append('-drive format=qcow2,file=%s,media=disk' % (os.path.realpath(guest)))
            # push the mount operation to the test shell pre-command to be run
            # before the test shell tries to execute.
            shell_precommand_list = []
            mountpoint = self.data['lava_test_results_dir']
            shell_precommand_list.append('mkdir %s' % mountpoint)
            shell_precommand_list.append('mount -L LAVA %s' % mountpoint)
            self.set_common_data('lava-test-shell', 'pre-command-list', shell_precommand_list)

        self.logger.info("Boot command: %s", ' '.join(self.sub_command))
        shell = ShellCommand(' '.join(self.sub_command), self.timeout, logger=self.logger)
        if shell.exitstatus:
            raise JobError("%s command exited %d: %s" % (self.sub_command, shell.exitstatus, shell.readlines()))
        self.logger.debug("started a shell command")

        shell_connection = ShellSession(self.job, shell)
        if not shell_connection.prompt_str and self.parameters['method'] == 'qemu':
            shell_connection.prompt_str = self.parameters['prompts']
        shell_connection = super(CallQemuAction, self).run(shell_connection, args)

        # FIXME: tests with multiple boots need to be handled too.
        self.data['boot-result'] = 'failed' if self.errors else 'success'
        return shell_connection


# FIXME: implement a QEMU protocol to monitor VM boots
