# Copyright (C) 2014 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
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

# List just the subclasses supported for this base strategy
# imported by the parser to populate the list of subclasses.

from lava_dispatcher.pipeline.action import (
    Action,
    Pipeline,
    Timeout,
    InfrastructureError,
)
from lava_dispatcher.pipeline.logical import Boot
from lava_dispatcher.pipeline.actions.boot import BootAction, AutoLoginAction
from lava_dispatcher.pipeline.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.pipeline.shell import ExpectShellSession
from lava_dispatcher.pipeline.connections.serial import ConnectDevice
from lava_dispatcher.pipeline.power import (
    ResetDevice,
    PowerOff
)
from lava_dispatcher.pipeline.utils.constants import (
    BOOT_MESSAGE,
    GRUB_BOOT_PROMPT,
    BOOTLOADER_DEFAULT_CMD_TIMEOUT
)
from lava_dispatcher.pipeline.utils.strings import substitute
from lava_dispatcher.pipeline.utils.network import dispatcher_ip


def bootloader_accepts(device, parameters):
    if 'method' not in parameters:
        raise RuntimeError("method not specified in boot parameters")
    if parameters['method'] != 'grub':
        return False
    if 'actions' not in device:
        raise RuntimeError("Invalid device configuration")
    if 'boot' not in device['actions']:
        return False
    if 'methods' not in device['actions']['boot']:
        raise RuntimeError("Device misconfiguration")
    return True


class Grub(Boot):

    compatibility = 3

    def __init__(self, parent, parameters):
        super(Grub, self).__init__(parent)
        self.action = GrubMainAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if not bootloader_accepts(device, parameters):
            return False
        return 'grub' in device['actions']['boot']['methods']


class GrubMainAction(BootAction):
    def __init__(self):
        super(GrubMainAction, self).__init__()
        self.name = "grub-main-action"
        self.description = "main grub boot action"
        self.summary = "run grub boot from power to system"
        self.expect_shell = True

    def validate(self):
        super(GrubMainAction, self).validate()

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(BootloaderCommandOverlay())
        self.internal_pipeline.add_action(ConnectDevice())
        self.internal_pipeline.add_action(ResetDevice())
        self.internal_pipeline.add_action(BootloaderInterrupt())
        self.internal_pipeline.add_action(BootloaderCommandsAction())
        if parameters.get("expect-shell", True):
            self.internal_pipeline.add_action(AutoLoginAction())
            self.internal_pipeline.add_action(ExpectShellSession())  # wait
            self.internal_pipeline.add_action(ExportDeviceEnvironment())
        else:
            self.expect_shell = False
            self.logger.debug("expect-shell was false, waiting for installer to complete")
            self.logger.debug("Doing a boot without a shell (installer)")
            self.internal_pipeline.add_action(InstallerWait())
            self.internal_pipeline.add_action(PowerOff())

    def run(self, connection, args=None):
        connection = super(GrubMainAction, self).run(connection, args)
        if self.expect_shell:
            self.logger.debug("Setting default test shell prompt")
            if not connection.prompt_str:
                connection.prompt_str = self.parameters['prompts']
            connection.timeout = self.connection_timeout
            self.wait(connection)
        self.data['boot-result'] = 'failed' if self.errors else 'success'
        return connection


class BootloaderInterrupt(Action):
    """
    Support for interrupting the bootloader.
    """
    def __init__(self):
        super(BootloaderInterrupt, self).__init__()
        self.name = "bootloader-interrupt"
        self.description = "interrupt bootloader"
        self.summary = "interrupt bootloader to get a prompt"
        self.type = "grub"

    def validate(self):
        super(BootloaderInterrupt, self).validate()
        hostname = self.job.device['hostname']
        # boards which are reset manually can be supported but errors have to handled manually too.
        if self.job.device.power_state in ['on', 'off']:
            # to enable power to a device, either power_on or hard_reset are needed.
            if self.job.device.power_command is '':
                self.errors = "Unable to power on or reset the device %s" % hostname
            if self.job.device.connect_command is '':
                self.errors = "Unable to connect to device %s" % hostname
        else:
            self.logger.debug("%s may need manual intervention to reboot" % hostname)
        device_methods = self.job.device['actions']['boot']['methods']
        if 'bootloader_prompt' not in device_methods[self.type]['parameters']:
            self.errors = "Missing bootloader prompt for device"

    def run(self, connection, args=None):
        if not connection:
            raise RuntimeError("%s started without a connection already in use" % self.name)
        connection = super(BootloaderInterrupt, self).run(connection, args)
        self.logger.debug("Changing prompt to '%s'", GRUB_BOOT_PROMPT)
        # device is to be put into a reset state, either by issuing 'reboot' or power-cycle
        connection.prompt_str = GRUB_BOOT_PROMPT
        self.wait(connection)
        connection.sendline("c")
        return connection


class InstallerWait(Action):
    """
    Wait for the non-interactive installer to finished
    """
    def __init__(self):
        super(InstallerWait, self).__init__()
        self.name = "installer-wait"
        self.description = "installer wait"
        self.summary = "wait for task to finish match arbitrary string"
        self.type = "grub"

    def validate(self):
        super(InstallerWait, self).validate()
        if "boot-finished" not in self.parameters:
            self.errors = "Missing boot-finished string"

    def run(self, connection, args=None):
        connection = super(InstallerWait, self).run(connection, args)
        wait_string = self.parameters['boot-finished']
        self.logger.debug("Not expecting a shell, so waiting for boot-finished: %s", wait_string)
        connection.prompt_str = wait_string
        self.wait(connection)
        self.data['boot-result'] = 'failed' if self.errors else 'success'
        return connection


class BootloaderCommandOverlay(Action):
    """
    Replace KERNEL_ADDR and DTB placeholders with the actual values for this
    particular pipeline.
    addresses are read from the device configuration parameters
    bootloader_type is determined from the boot action method strategy
    bootz or bootm is determined by boot action method type. (i.e. it is up to
    the test writer to select the correct download file for the correct boot command.)
    server_ip is calculated at runtime
    filenames are determined from the download Action.
    """
    def __init__(self):
        super(BootloaderCommandOverlay, self).__init__()
        self.name = "bootloader-overlay"
        self.summary = "replace placeholders with job data"
        self.description = "substitute job data into bootloader command list"
        self.commands = None
        self.type = "grub"

    def validate(self):
        super(BootloaderCommandOverlay, self).validate()
        device_methods = self.job.device['actions']['boot']['methods']
        if self.type not in self.job.device['actions']['boot']['methods']:
            self.errors = "grub boot method not found"
        if 'method' not in self.parameters:
            self.errors = "missing method"
        elif 'commands' not in self.parameters:
            self.errors = "missing commands"
        elif self.parameters['commands'] not in device_methods[self.parameters['method']]:
            self.errors = "Command not found in supported methods"
        elif 'commands' not in device_methods[self.parameters['method']][self.parameters['commands']]:
            self.errors = "No commands found in parameters"
        # download_action will set ['dtb'] as tftp_path, tmpdir & filename later, in the run step.
        self.data.setdefault(self.type, {})
        self.data[self.type].setdefault('commands', [])
        self.commands = device_methods[self.parameters['method']][self.parameters['commands']]['commands']

    def run(self, connection, args=None):
        """
        Read data from the download action and replace in context
        Use common data for all values passed into the substitutions so that
        multiple actions can use the same code.
        """
        # Multiple deployments would overwrite the value if parsed in the validate step.
        # FIXME: implement isolation for repeated steps.
        connection = super(BootloaderCommandOverlay, self).run(connection, args)
        try:
            ip_addr = dispatcher_ip()
        except InfrastructureError as exc:
            raise RuntimeError("Unable to get dispatcher IP address: %s" % exc)
        substitutions = {
            '{SERVER_IP}': ip_addr
        }
        substitutions['{PRESEED_CONFIG}'] = self.get_common_data('file', 'preseed')
        substitutions['{DTB}'] = self.get_common_data('file', 'dtb')
        substitutions['{RAMDISK}'] = self.get_common_data('file', 'ramdisk')
        substitutions['{KERNEL}'] = self.get_common_data('file', 'kernel')
        nfs_url = self.get_common_data('nfs_url', 'nfsroot')
        if 'download_action' in self.data and 'nfsrootfs' in self.data['download_action']:
            substitutions['{NFSROOTFS}'] = self.get_common_data('file', 'nfsroot')
            substitutions['{NFS_SERVER_IP}'] = ip_addr
        elif nfs_url:
            substitutions['{NFSROOTFS}'] = nfs_url
            substitutions['{NFS_SERVER_IP}'] = self.get_common_data('nfs_url', 'serverip')

        substitutions['{ROOT}'] = self.get_common_data('uuid', 'root')  # UUID label, not a file
        substitutions['{ROOT_PART}'] = self.get_common_data('uuid', 'boot_part')

        self.data[self.type]['commands'] = substitute(self.commands, substitutions)
        self.logger.debug("Parsed boot commands: %s" % '; '.join(self.data[self.type]['commands']))
        return connection


class BootloaderCommandsAction(Action):
    """
    Send the boot commands to the bootloader
    """
    def __init__(self):
        super(BootloaderCommandsAction, self).__init__()
        self.name = "bootloader-commands"
        self.description = "send commands to bootloader"
        self.summary = "interactive bootloader"
        self.params = None
        self.timeout = Timeout(self.name, BOOTLOADER_DEFAULT_CMD_TIMEOUT)
        self.type = "grub"

    def validate(self):
        super(BootloaderCommandsAction, self).validate()
        if self.type not in self.data:
            self.errors = "Unable to read bootloader context data"
        # get prompt_str from device parameters
        self.params = self.job.device['actions']['boot']['methods'][self.type]['parameters']

    def run(self, connection, args=None):
        if not connection:
            self.errors = "%s started without a connection already in use" % self.name
        connection = super(BootloaderCommandsAction, self).run(connection, args)
        connection.prompt_str = self.params['bootloader_prompt']
        self.logger.debug("Changing prompt to %s" % connection.prompt_str)
        self.wait(connection)
        i = 1
        for line in self.data[self.type]['commands']:
            connection.sendline(line, delay=100, send_char=True)
            if i != (len(self.data[self.type]['commands'])):
                self.wait(connection)
                i += 1
        # allow for auto_login
        connection.prompt_str = self.params.get('boot_message', BOOT_MESSAGE)
        self.logger.debug("Changing prompt to %s" % connection.prompt_str)
        self.wait(connection)
        return connection
