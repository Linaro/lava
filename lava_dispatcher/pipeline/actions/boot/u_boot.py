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

# List just the subclasses supported for this base strategy
# imported by the parser to populate the list of subclasses.

import os.path
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
from lava_dispatcher.pipeline.power import ResetDevice
from lava_dispatcher.pipeline.utils.constants import (
    UBOOT_AUTOBOOT_PROMPT,
    UBOOT_INTERRUPT_CHARACTER,
    UBOOT_DEFAULT_CMD_TIMEOUT,
    BOOT_MESSAGE,
)
from lava_dispatcher.pipeline.utils.strings import substitute
from lava_dispatcher.pipeline.utils.network import dispatcher_ip


def uboot_accepts(device, parameters):
    if 'method' not in parameters:
        raise RuntimeError("method not specified in boot parameters")
    if parameters['method'] != 'u-boot':
        return False
    if 'actions' not in device:
        raise RuntimeError("Invalid device configuration")
    if 'boot' not in device['actions']:
        return False
    if 'methods' not in device['actions']['boot']:
        raise RuntimeError("Device misconfiguration")
    return True


class UBoot(Boot):
    """
    The UBoot method prepares the command to run on the dispatcher but this
    command needs to start a new connection and then interrupt u-boot.
    An expect shell session can then be handed over to the UBootAction.
    self.run_command is a blocking call, so Boot needs to use
    a direct spawn call via ShellCommand (which wraps pexpect.spawn) then
    hand this pexpect wrapper to subsequent actions as a shell connection.
    """

    compatibility = 1

    def __init__(self, parent, parameters):
        super(UBoot, self).__init__(parent)
        self.action = UBootAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if not uboot_accepts(device, parameters):
            return False
        return 'u-boot' in device['actions']['boot']['methods']


class UBootAction(BootAction):
    """
    Wraps the Retry Action to allow for actions which precede
    the reset, e.g. Connect.
    """
    def __init__(self):
        super(UBootAction, self).__init__()
        self.name = "uboot-action"
        self.description = "interactive uboot action"
        self.summary = "pass uboot commands"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        # customize the device configuration for this job
        self.internal_pipeline.add_action(UBootPrepareKernelAction())
        self.internal_pipeline.add_action(UBootSecondaryMedia())
        self.internal_pipeline.add_action(UBootCommandOverlay())
        self.internal_pipeline.add_action(ConnectDevice())
        self.internal_pipeline.add_action(UBootRetry())


class ExpectBootloaderSession(Action):
    """
    Waits for a shell connection to the device for the current job.
    """

    def __init__(self):
        super(ExpectBootloaderSession, self).__init__()
        self.name = "expect-bootloader-connection"
        self.summary = "Expect a bootloader prompt"
        self.description = "Wait for a u-boot shell"

    def run(self, connection, args=None):
        connection = super(ExpectBootloaderSession, self).run(connection, args)
        device_methods = self.job.device['actions']['boot']['methods']
        connection.prompt_str = device_methods['u-boot']['parameters']['bootloader_prompt']
        self.logger.debug("%s: Waiting for prompt", self.name)
        self.wait(connection)
        return connection


class UBootRetry(BootAction):

    def __init__(self):
        super(UBootRetry, self).__init__()
        self.name = "uboot-retry"
        self.description = "interactive uboot retry action"
        self.summary = "uboot commands with retry"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        # establish a new connection before trying the reset
        self.internal_pipeline.add_action(ResetDevice())
        self.internal_pipeline.add_action(UBootInterrupt())
        # need to look for Hit any key to stop autoboot
        self.internal_pipeline.add_action(ExpectBootloaderSession())  # wait
        # and set prompt to the uboot prompt
        self.internal_pipeline.add_action(UBootCommandsAction())
        # Add AutoLoginAction unconditionally as this action does nothing if
        # the configuration does not contain 'auto_login'
        self.internal_pipeline.add_action(AutoLoginAction())
        self.internal_pipeline.add_action(ExpectShellSession())  # wait
        self.internal_pipeline.add_action(ExportDeviceEnvironment())

    def validate(self):
        super(UBootRetry, self).validate()
        self.set_common_data(
            'bootloader_prompt',
            'prompt',
            self.job.device['actions']['boot']['methods']['u-boot']['parameters']['bootloader_prompt']
        )

    def run(self, connection, args=None):
        connection = super(UBootRetry, self).run(connection, args)
        self.logger.debug("Setting default test shell prompt")
        if not connection.prompt_str:
            connection.prompt_str = self.parameters['prompts']
        self.logger.debug(connection.prompt_str)
        connection.timeout = self.connection_timeout
        self.wait(connection)
        # Log an error only when needed
        if self.errors:
            self.logger.error(self.errors)
            self.data['boot-result'] = 'failed'
        else:
            self.data['boot-result'] = 'success'
        return connection


class UBootInterrupt(Action):
    """
    Support for interrupting the bootloader.
    """
    def __init__(self):
        super(UBootInterrupt, self).__init__()
        self.name = "u-boot-interrupt"
        self.description = "interrupt u-boot"
        self.summary = "interrupt u-boot to get a prompt"

    def validate(self):
        super(UBootInterrupt, self).validate()
        hostname = self.job.device['hostname']
        # boards which are reset manually can be supported but errors have to handled manually too.
        if self.job.device.power_state in ['on', 'off']:
            # to enable power to a device, either power_on or hard_reset are needed.
            if self.job.device.power_command is '':
                self.errors = "Unable to power on or reset the device %s" % hostname
            if self.job.device.connect_command is '':
                self.errors = "Unable to connect to device %s" % hostname
        else:
            self.logger.debug("%s may need manual intervention to reboot", hostname)
        device_methods = self.job.device['actions']['boot']['methods']
        if 'bootloader_prompt' not in device_methods['u-boot']['parameters']:
            self.errors = "Missing bootloader prompt for device"

    def run(self, connection, args=None):
        if not connection:
            raise RuntimeError("%s started without a connection already in use" % self.name)
        connection = super(UBootInterrupt, self).run(connection, args)
        device_methods = self.job.device['actions']['boot']['methods']
        # device is to be put into a reset state, either by issuing 'reboot' or power-cycle
        interrupt_prompt = device_methods['u-boot']['parameters'].get('interrupt_prompt', UBOOT_AUTOBOOT_PROMPT)
        interrupt_char = device_methods['u-boot']['parameters'].get('interrupt_char', UBOOT_INTERRUPT_CHARACTER)
        self.logger.debug("Changing prompt to '%s'", interrupt_prompt)
        connection.prompt_str = interrupt_prompt
        self.wait(connection)
        connection.sendline('%s\n' % interrupt_char)
        connection.prompt_str = device_methods['u-boot']['parameters']['bootloader_prompt']
        self.wait(connection)
        return connection


class UBootSecondaryMedia(Action):
    """
    Idempotent action which sets the static data only used when this is a boot of secondary media
    already deployed.
    """
    def __init__(self):
        super(UBootSecondaryMedia, self).__init__()
        self.name = "uboot-from-media"
        self.summary = "set uboot strings for deployed media"
        self.description = "let uboot know where to find the kernel in the image on secondary media"

    def validate(self):
        super(UBootSecondaryMedia, self).validate()
        if 'media' not in self.job.device['parameters']:
            return
        media_keys = self.job.device['parameters']['media'].keys()
        if self.parameters['commands'] not in media_keys:
            return
        if 'kernel' not in self.parameters:
            self.errors = "Missing kernel location"
        # ramdisk does not have to be specified, nor dtb
        if 'root_uuid' not in self.parameters:
            # FIXME: root_node also needs to be supported
            self.errors = "Missing UUID of the roofs inside the deployed image"
        if 'boot_part' not in self.parameters:
            self.errors = "Missing boot_part for the partition number of the boot files inside the deployed image"

        self.set_common_data('file', 'kernel', self.parameters.get('kernel', ''))
        self.set_common_data('file', 'ramdisk', self.parameters.get('ramdisk', ''))
        self.set_common_data('file', 'dtb', self.parameters.get('dtb', ''))
        self.set_common_data('uuid', 'root', self.parameters['root_uuid'])
        media_params = self.job.device['parameters']['media'][self.parameters['commands']]
        if self.get_common_data('u-boot', 'device') not in media_params:
            self.errors = "%s does not match requested media type %s" % (
                self.get_common_data('u-boot', 'device'), self.parameters['commands']
            )
        if not self.valid:
            return
        self.set_common_data(
            'uuid',
            'boot_part',
            '%s:%s' % (
                media_params[self.get_common_data('u-boot', 'device')]['device_id'],
                self.parameters['boot_part']
            )
        )


class UBootCommandOverlay(Action):
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
        super(UBootCommandOverlay, self).__init__()
        self.name = "uboot-overlay"
        self.summary = "replace placeholders with job data"
        self.description = "substitute job data into uboot command list"
        self.commands = None

    def validate(self):
        super(UBootCommandOverlay, self).validate()
        device_methods = self.job.device['actions']['boot']['methods']
        if 'method' not in self.parameters:
            self.errors = "missing method"
        # FIXME: allow u-boot commands in the job definition (which make this type a list)
        elif 'commands' not in self.parameters:
            self.errors = "missing commands"
        elif self.parameters['commands'] not in device_methods[self.parameters['method']]:
            self.errors = "Command not found in supported methods"
        elif 'commands' not in device_methods[self.parameters['method']][self.parameters['commands']]:
            self.errors = "No commands found in parameters"
        # download_action will set ['dtb'] as tftp_path, tmpdir & filename later, in the run step.
        self.data.setdefault('u-boot', {})
        self.data['u-boot'].setdefault('commands', [])
        if 'type' not in self.parameters:
            self.errors = "No boot type specified in device parameters."
        else:
            if self.parameters['type'] not in self.job.device['parameters']:
                self.errors = "Unable to match specified boot type '%s' with device parameters" % self.parameters['type']
        self.commands = device_methods[self.parameters['method']][self.parameters['commands']]['commands']

    def run(self, connection, args=None):
        """
        Read data from the download action and replace in context
        Use common data for all values passed into the substitutions so that
        multiple actions can use the same code.
        """
        # Multiple deployments would overwrite the value if parsed in the validate step.
        # FIXME: implement isolation for repeated steps.
        connection = super(UBootCommandOverlay, self).run(connection, args)
        try:
            ip_addr = dispatcher_ip()
        except InfrastructureError as exc:
            raise RuntimeError("Unable to get dispatcher IP address: %s" % exc)
        substitutions = {
            '{SERVER_IP}': ip_addr
        }

        kernel_addr = self.job.device['parameters'][self.parameters['type']]['kernel']
        dtb_addr = self.job.device['parameters'][self.parameters['type']]['dtb']
        ramdisk_addr = self.job.device['parameters'][self.parameters['type']]['ramdisk']

        substitutions['{KERNEL_ADDR}'] = kernel_addr
        substitutions['{DTB_ADDR}'] = dtb_addr
        substitutions['{RAMDISK_ADDR}'] = ramdisk_addr
        if not self.get_common_data('tftp', 'ramdisk') and not self.get_common_data('file', 'ramdisk'):
            ramdisk_addr = '-'
        bootcommand = self.parameters['type']
        if self.parameters['type'] == 'uimage':
            bootcommand = 'bootm'
        elif self.parameters['type'] == 'zimage':
            bootcommand = 'bootz'
        elif self.parameters['type'] == 'image':
            bootcommand = 'booti'
        substitutions['{BOOTX}'] = "%s %s %s %s" % (
            bootcommand, kernel_addr, ramdisk_addr, dtb_addr)

        substitutions['{RAMDISK}'] = self.get_common_data('file', 'ramdisk')
        substitutions['{KERNEL}'] = self.get_common_data('file', 'kernel')
        substitutions['{DTB}'] = self.get_common_data('file', 'dtb')

        nfs_url = self.get_common_data('nfs_url', 'nfsroot')
        if 'download_action' in self.data and 'nfsrootfs' in self.data['download_action']:
            substitutions['{NFSROOTFS}'] = self.get_common_data('file', 'nfsroot')
            substitutions['{NFS_SERVER_IP}'] = ip_addr
        elif nfs_url:

            substitutions['{NFSROOTFS}'] = nfs_url
            substitutions['{NFS_SERVER_IP}'] = self.get_common_data('nfs_url', 'serverip')

        substitutions['{ROOT}'] = self.get_common_data('uuid', 'root')  # UUID label, not a file
        substitutions['{ROOT_PART}'] = self.get_common_data('uuid', 'boot_part')

        self.data.setdefault('u-boot', {})
        self.data['u-boot']['commands'] = substitute(self.commands, substitutions)
        self.logger.debug("Parsed boot commands: %s", '; '.join(self.data['u-boot']['commands']))
        return connection


class UBootCommandsAction(Action):
    """
    Send the ramdisk commands to u-boot
    """
    def __init__(self):
        super(UBootCommandsAction, self).__init__()
        self.name = "u-boot-commands"
        self.description = "send commands to u-boot"
        self.summary = "interactive u-boot"
        self.params = None
        self.timeout = Timeout(self.name, UBOOT_DEFAULT_CMD_TIMEOUT)

    def validate(self):
        super(UBootCommandsAction, self).validate()
        if 'u-boot' not in self.data:
            self.errors = "Unable to read uboot context data"
        # get prompt_str from device parameters
        self.params = self.job.device['actions']['boot']['methods']['u-boot']['parameters']

    def run(self, connection, args=None):
        if not connection:
            self.errors = "%s started without a connection already in use" % self.name
        connection = super(UBootCommandsAction, self).run(connection, args)
        connection.prompt_str = self.params['bootloader_prompt']
        self.logger.debug("Changing prompt to %s", connection.prompt_str)
        for line in self.data['u-boot']['commands']:
            self.wait(connection)
            connection.sendline(line, delay=self.character_delay)
        # allow for auto_login
        params = self.job.device['actions']['boot']['methods']['u-boot']['parameters']
        connection.prompt_str = params.get('boot_message', BOOT_MESSAGE)
        self.logger.debug("Changing prompt to %s", connection.prompt_str)
        self.wait(connection)
        return connection


class UBootPrepareKernelAction(Action):
    """
    Convert kernels to uImage or append DTB, if needed
    """
    def __init__(self):
        super(UBootPrepareKernelAction, self).__init__()
        self.name = "uboot-prepare-kernel"
        self.description = "convert kernel to uimage or append dtb"
        self.summary = "prepare/convert kernel"
        self.type = None
        self.params = None
        self.kernel_type = None

    def create_uimage(self, kernel, load_addr, xip, arch, output):  # pylint: disable=too-many-arguments
        load_addr = int(load_addr, 16)
        uimage_path = '%s/%s' % (os.path.dirname(kernel), output)
        if xip:
            entry_addr = load_addr + 64
        else:
            entry_addr = load_addr
        cmd = "mkimage -A %s -O linux -T kernel" \
              " -C none -a 0x%x -e 0x%x" \
              " -d %s %s" % (arch, load_addr,
                             entry_addr, kernel,
                             uimage_path)
        if self.run_command(cmd.split(' ')):
            return uimage_path
        else:
            raise InfrastructureError("uImage creation failed")

    def validate(self):
        super(UBootPrepareKernelAction, self).validate()
        self.params = self.job.device['actions']['boot']['methods']['u-boot']['parameters']
        self.kernel_type = self.get_common_data('type', 'kernel')
        if 'type' in self.parameters:
            self.type = str(self.parameters['type']).lower()
        if self.type:
            if self.type not in self.job.device['parameters']:
                self.errors = "Requested kernel boot type '%s' not supported by this device." % self.type
            if self.type == "bootm" or self.type == "bootz" or self.type == "booti":
                self.logger.info("booti, bootm and bootz are being deprecated soon, please use 'image','uimage' or 'zimage'")
        if self.kernel_type:
            self.kernel_type = str(self.kernel_type).lower()
            if self.type != self.kernel_type:
                if 'mkimage_arch' not in self.params:
                    self.errors = "Missing architecture for uboot mkimage support (mkimage_arch in u-boot parameters)"
                if self.type == 'zimage' and self.kernel_type == 'uimage':
                    self.errors = "Can't convert a uimage to zimage"
                elif self.type == 'zimage' and self.kernel_type == 'image':
                    self.errors = "Can't convert an image to zimage"
                elif self.type == 'image' and self.kernel_type == 'zimage':
                    self.errors = "Can't convert a zimage to image"

    def run(self, connection, args=None):
        connection = super(UBootPrepareKernelAction, self).run(connection, args)
        if not self.kernel_type:
            return connection  # idempotency
        old_kernel = self.get_common_data('file', 'kernel')
        filename = self.data['download_action']['kernel']['file']
        load_addr = self.job.device['parameters'][self.type]['kernel']
        if 'text_offset' in self.job.device['parameters']:
            load_addr = self.job.device['parameters']['text_offset']
        arch = self.params['mkimage_arch']
        if (self.type == "uimage" or self.type == "bootm") and self.kernel_type == "image":
            self.logger.debug("Converting image to uimage")
            self.create_uimage(filename, load_addr, False, arch, 'uImage')
            new_kernel = os.path.dirname(old_kernel) + '/uImage'
            self.set_common_data('file', 'kernel', new_kernel)
        elif (self.type == "uimage" or self.type == "bootm") and self.kernel_type == "zimage":
            self.logger.debug("Converting zimage to uimage")
            self.create_uimage(filename, load_addr, False, arch, 'uImage')
            new_kernel = os.path.dirname(old_kernel) + '/uImage'
            self.set_common_data('file', 'kernel', new_kernel)
        return connection
