# Copyright (C) 2016 Linaro Limited
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
from lava_dispatcher.pipeline.action import Action, JobError, Pipeline, InfrastructureError
from lava_dispatcher.pipeline.logical import Boot
from lava_dispatcher.pipeline.actions.boot import BootAction
from lava_dispatcher.pipeline.utils.shell import which, wait_for_prompt
from lava_dispatcher.pipeline.utils.strings import substitute
from lava_dispatcher.pipeline.utils.constants import INSTALLER_QUIET_MSG
from lava_dispatcher.pipeline.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.pipeline.shell import (
    ExpectShellSession,
    ShellCommand,
    ShellSession
)
from lava_dispatcher.pipeline.actions.boot import AutoLoginAction


class BootIsoInstaller(Boot):

    compatibility = 3

    def __init__(self, parent, parameters):
        super(BootIsoInstaller, self).__init__(parent)
        self.action = BootIsoInstallerAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if 'media' in parameters and parameters['media'] == 'img':
            if 'method' in parameters and parameters['method'] == 'qemu-iso':
                return True
        return False


class BootIsoInstallerAction(BootAction):

    def __init__(self):
        super(BootIsoInstallerAction, self).__init__()
        self.name = 'boot_installer_iso'
        self.description = "boot installer with preseed"
        self.summary = "boot installer iso image"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(IsoCommandLine())
        self.internal_pipeline.add_action(MonitorInstallerSession())
        self.internal_pipeline.add_action(IsoRebootAction())
        # Add AutoLoginAction unconditionally as this action does nothing if
        # the configuration does not contain 'auto_login'
        self.internal_pipeline.add_action(AutoLoginAction())
        self.internal_pipeline.add_action(ExpectShellSession())
        self.internal_pipeline.add_action(ExportDeviceEnvironment())


class IsoCommandLine(Action):  # pylint: disable=too-many-instance-attributes

    """
    qemu-system-x86_64 -nographic -enable-kvm -cpu host -net nic,model=virtio,macaddr=52:54:00:12:34:59 -net user -m 2048 \
    -drive format=raw,file=hd_img.img -drive file=${NAME},index=2,media=cdrom,readonly \
    -boot c -no-reboot -kernel vmlinuz -initrd initrd.gz \
    -append "\"${BASE} ${LOCALE} ${CONSOLE} ${KEYMAPS} ${NETCFG} preseed/url=${PRESEED_URL} --- ${CONSOLE}\"" \
    """

    def __init__(self):
        super(IsoCommandLine, self).__init__()
        self.name = 'execute-installer-command'
        self.summary = 'include downloaded locations and call qemu'
        self.description = 'add dynamic data values to command line and execute'

    def run(self, connection, max_end_time, args=None):
        # substitutions
        substitutions = {'{emptyimage}': self.get_namespace_data(action='prepare-empty-image', label='prepare-empty-image', key='output')}
        sub_command = self.get_namespace_data(action='prepare-qemu-commands', label='prepare-qemu-commands', key='sub_command')
        sub_command = substitute(sub_command, substitutions)
        command_line = ' '.join(sub_command)

        commands = []
        # get the download args in run()
        image_arg = self.get_namespace_data(action='download_action', label='iso', key='image_arg')
        action_arg = self.get_namespace_data(action='download_action', label='iso', key='file')
        substitutions["{%s}" % 'iso'] = action_arg
        commands.append(image_arg)
        command_line += ' '.join(substitute(commands, substitutions))

        preseed_file = self.get_namespace_data(action='download_action', label='file', key='preseed')
        if not preseed_file:
            raise JobError("Unable to identify downloaded preseed filename.")
        substitutions = {'{preseed}': preseed_file}
        append_args = self.get_namespace_data(action='prepare-qemu-commands', label='prepare-qemu-commands', key='append')
        append_args = substitute([append_args], substitutions)
        command_line += ' '.join(append_args)

        self.logger.info(command_line)
        shell = ShellCommand(command_line, self.timeout, logger=self.logger)
        if shell.exitstatus:
            raise JobError("%s command exited %d: %s" % (sub_command[0], shell.exitstatus, shell.readlines()))
        self.logger.debug("started a shell command")

        shell_connection = ShellSession(self.job, shell)
        shell_connection.prompt_str = self.get_namespace_data(
            action='prepare-qemu-commands', label='prepare-qemu-commands', key='prompts')
        shell_connection = super(IsoCommandLine, self).run(shell_connection, max_end_time, args)
        return shell_connection


class MonitorInstallerSession(Action):
    """
    Waits for a shell connection to the device for the current job.
    The shell connection can be over any particular connection,
    all that is needed is a prompt.
    """
    compatibility = 3

    def __init__(self):
        super(MonitorInstallerSession, self).__init__()
        self.name = "monitor-installer-connection"
        self.summary = "Watch for error strings or end of install"
        self.description = "Monitor installer operation"

    def validate(self):
        super(MonitorInstallerSession, self).validate()
        if 'prompts' not in self.parameters:
            self.errors = "Unable to identify test image prompts from parameters."

    def run(self, connection, max_end_time, args=None):
        self.logger.debug("%s: Waiting for prompt %s", self.name, ' '.join(connection.prompt_str))
        wait_for_prompt(connection.raw_connection, connection.prompt_str, connection.timeout.duration, '#')
        return connection


class IsoRebootAction(Action):

    def __init__(self):
        super(IsoRebootAction, self).__init__()
        self.name = 'reboot-into-installed'
        self.summary = 'reboot into installed image'
        self.description = 'reboot and login to the new system'
        self.sub_command = None

    def validate(self):
        super(IsoRebootAction, self).validate()
        if 'prompts' not in self.parameters:
            self.errors = "Unable to identify boot prompts from job definition."
        try:
            boot = self.job.device['actions']['boot']['methods']['qemu']
            qemu_binary = which(boot['parameters']['command'])
            self.sub_command = [qemu_binary]
            self.sub_command.extend(boot['parameters'].get('options', []))
        except AttributeError as exc:
            raise InfrastructureError(exc)
        except (KeyError, TypeError):
            self.errors = "Invalid parameters for %s" % self.name

    def run(self, connection, max_end_time, args=None):
        """
        qemu needs help to reboot after running the debian installer
        and typically the boot is quiet, so there is almost nothing to log.
        """
        base_image = self.get_namespace_data(action='prepare-empty-image', label='prepare-empty-image', key='output')
        self.sub_command.append('-drive format=raw,file=%s' % base_image)
        guest = self.get_namespace_data(action='apply-overlay-guest', label='guest', key='filename')
        if guest:
            self.logger.info("Extending command line for qcow2 test overlay")
            self.sub_command.append('-drive format=qcow2,file=%s,media=disk' % (os.path.realpath(guest)))
            # push the mount operation to the test shell pre-command to be run
            # before the test shell tries to execute.
            shell_precommand_list = []
            mountpoint = self.get_namespace_data(action='test', label='results', key='lava_test_results_dir')
            shell_precommand_list.append('mkdir %s' % mountpoint)
            shell_precommand_list.append('mount -L LAVA %s' % mountpoint)
            self.set_namespace_data(action='test', label='lava-test-shell', key='pre-command-list', value=shell_precommand_list)

        self.logger.info("Boot command: %s", ' '.join(self.sub_command))
        shell = ShellCommand(' '.join(self.sub_command), self.timeout, logger=self.logger)
        if shell.exitstatus:
            raise JobError("%s command exited %d: %s" % (self.sub_command, shell.exitstatus, shell.readlines()))
        self.logger.debug("started a shell command")

        shell_connection = ShellSession(self.job, shell)
        shell_connection = super(IsoRebootAction, self).run(shell_connection, max_end_time, args)
        shell_connection.prompt_str = [INSTALLER_QUIET_MSG]
        self.wait(shell_connection)
        res = 'failed' if self.errors else 'success'
        self.set_namespace_data(action='boot', label='shared', key='boot-result', value=res)
        self.set_namespace_data(action='shared', label='shared', key='connection', value=shell_connection)
        self.logger.debug("boot-result: %s", res)
        return shell_connection
