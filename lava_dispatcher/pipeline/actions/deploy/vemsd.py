# Copyright (C) 2017 Linaro Limited
#
# Author: Dean Arnold <dean.arnold@linaro.org>
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

import os
import shutil
from lava_dispatcher.pipeline.action import (
    Action,
    ConfigurationError,
    JobError,
    InfrastructureError,
    LAVABug,
    Pipeline,
)
from lava_dispatcher.pipeline.logical import Deployment
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.deploy.download import DownloaderAction
from lava_dispatcher.pipeline.connections.serial import ConnectDevice
from lava_dispatcher.pipeline.power import PowerOn
from lava_dispatcher.pipeline.utils.udev import WaitUSBMassStorageDeviceAction
from lava_dispatcher.pipeline.utils.constants import (
    VEXPRESS_AUTORUN_INTERRUPT_CHARACTER,
)
from lava_dispatcher.pipeline.utils.filesystem import (
    decompress_file,
    copy_directory_contents,
    remove_directory_contents,
)


def vexpress_fw_accept(device, parameters):
    """
    Each VExpress FW deployment strategy uses these
    checks as a base
    """
    if 'to' not in parameters:
        return False
    if parameters['to'] != 'vemsd':
        return False
    if not device:
        return False
    if 'actions' not in device:
        raise ConfigurationError("Invalid device configuration")
    if 'deploy' not in device['actions']:
        return False
    if 'methods' not in device['actions']['deploy']:
        raise ConfigurationError("Device misconfiguration")
    return True


class VExpressMsd(Deployment):
    """
    Strategy class for a Versatile Express firmware deployment.
    Downloads Versatile Express board recovery image and deploys
    to target device
    """
    compatibility = 1

    def __init__(self, parent, parameters):
        super(VExpressMsd, self).__init__(parent)
        self.action = VExpressMsdAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if not vexpress_fw_accept(device, parameters):
            return False
        if 'vemsd' in device['actions']['deploy']['methods']:
            return True
        return False


class VExpressMsdAction(DeployAction):
    """
    Action for deploying firmware to a Versatile Express board
    in the form of a board recovery image.
    """
    def __init__(self):
        super(VExpressMsdAction, self).__init__()
        self.name = "vexpress-fw-deploy"
        self.description = "deploy vexpress board recovery image"
        self.summary = "VExpress FW deployment"

    def validate(self):
        super(VExpressMsdAction, self).validate()
        if not self.valid:
            return
        if not self.parameters.get('recovery_image', None):  # idempotency
            return

    def populate(self, parameters):
        download_dir = self.mkdtemp()
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if 'recovery_image' in parameters:
            download = DownloaderAction('recovery_image', path=download_dir)
            download.max_retries = 3
            self.internal_pipeline.add_action(download)
        if hasattr(self.job.device, 'power_state'):
            if self.job.device.power_state in ['on', 'off']:
                self.force_prompt = True
                self.internal_pipeline.add_action(ConnectDevice())
                self.internal_pipeline.add_action(PowerOn())
        self.internal_pipeline.add_action(ExtractVExpressRecoveryImage())
        self.internal_pipeline.add_action(EnterVExpressMCC())
        self.internal_pipeline.add_action(EnableVExpressMassStorage())
        self.internal_pipeline.add_action(WaitUSBMassStorageDeviceAction())
        self.internal_pipeline.add_action(MountVExpressMassStorageDevice())
        self.internal_pipeline.add_action(DeployVExpressRecoveryImage())
        self.internal_pipeline.add_action(UnmountVExpressMassStorageDevice())
        self.internal_pipeline.add_action(VExpressFlashErase())


class ExtractVExpressRecoveryImage(Action):
    """
    Unpacks the Versatile Express Board Recovery Image
    """
    def __init__(self):
        super(ExtractVExpressRecoveryImage, self).__init__()
        self.name = "extract-vexpress-recovery-image"
        self.description = "unpack versatile express recovery image"
        self.summary = "unpack versatile express recovery image ready for deployment"
        self.param_key = 'recovery_image'
        self.file_key = "recovery_image"
        self.compression = None

    def validate(self):
        super(ExtractVExpressRecoveryImage, self).validate()
        if not self.get_namespace_data(
                action='download_action', label=self.param_key, key='file'):
            self.errors = "no file specified extract as %s" % self.param_key
        self.compression = self.parameters[self.file_key].get('compression', None)
        if not self.compression:
            self.errors = "no compression set for recovery image"

    def run(self, connection, max_end_time, args=None):
        if not self.parameters.get(self.param_key, None):  # idempotency
            return connection
        connection = super(ExtractVExpressRecoveryImage, self).run(connection, max_end_time, args)

        # copy recovery image to a temporary directory and unpack
        recovery_image = self.get_namespace_data(action='download_action', label=self.param_key, key='file')
        recovery_image_dir = self.mkdtemp()
        shutil.copy(recovery_image, recovery_image_dir)
        tmp_recovery_image = os.path.join(recovery_image_dir, os.path.basename(recovery_image))

        if os.path.isfile(tmp_recovery_image):
            decompress_file(tmp_recovery_image, self.compression)
            os.remove(tmp_recovery_image)
            self.set_namespace_data(action='extract-vexpress-recovery-image', label='file', key=self.file_key, value=recovery_image_dir)
            self.logger.debug("Extracted %s to %s", self.file_key, recovery_image_dir)
        else:
            raise InfrastructureError("Unable to decompress recovery image")
        return connection


class EnterVExpressMCC(Action):
    """
    Interrupts autorun if necessary and enters Versatile Express MCC.
    From here commands can be issued for enabling USB and erasing flash
    """
    def __init__(self):
        super(EnterVExpressMCC, self).__init__()
        self.name = "enter-vexpress-mcc"
        self.description = "enter Versatile Express MCC"
        self.summary = "enter Versatile Express MCC, interrupting autorun if needed"
        self.device_params = None
        self.interrupt_char = None
        self.mcc_prompt = None
        self.autorun_prompt = None

    def validate(self):
        super(EnterVExpressMCC, self).validate()
        if not self.valid:
            return
        self.device_params = self.job.device['actions']['deploy']['methods']['vemsd']['parameters']
        self.interrupt_char = self.device_params.get('interrupt_char', VEXPRESS_AUTORUN_INTERRUPT_CHARACTER)
        self.mcc_prompt = self.device_params.get('mcc_prompt', None)
        self.autorun_prompt = self.device_params.get('autorun_prompt', None)
        if not isinstance(self.mcc_prompt, str):
            self.errors = 'Versatile Express MCC prompt unset'
        if not isinstance(self.autorun_prompt, str):
            self.errors = 'Versatile Express autorun prompt unset'

    def run(self, connection, max_end_time, args=None):
        if not connection:
            raise LAVABug("%s started without a connection already in use" % self.name)
        connection = super(EnterVExpressMCC, self).run(connection, max_end_time, args)

        # Get possible prompts from device config
        connection.prompt_str = [self.autorun_prompt, self.mcc_prompt]

        self.logger.debug("Changing prompt to '%s'", connection.prompt_str)
        index = self.wait(connection)
        if connection.prompt_str[index] != self.mcc_prompt:
            self.logger.debug('Autorun enabled: interrupting..')
            connection.sendline('%s\n' % self.interrupt_char)
            connection.prompt_str = self.mcc_prompt
            self.wait(connection)
        else:
            self.logger.debug('Already at MCC prompt: autorun looks to be disabled')
        return connection


class EnableVExpressMassStorage(Action):
    """
    Enable Versatile Express USB mass storage device from the MCC prompt
    """
    def __init__(self):
        super(EnableVExpressMassStorage, self).__init__()
        self.name = "enable-vexpress-usbmsd"
        self.description = "enable vexpress usb msd"
        self.summary = "enable vexpress usb mass storage device"
        self.mcc_prompt = None
        self.mcc_cmd = None

    def validate(self):
        super(EnableVExpressMassStorage, self).validate()
        device_params = self.job.device['actions']['deploy']['methods']['vemsd']['parameters']
        self.mcc_prompt = device_params.get('mcc_prompt')
        self.mcc_cmd = device_params.get('msd_mount_cmd')
        if not isinstance(self.mcc_prompt, str):
            self.errors = 'Versatile Express MCC prompt unset'
        if not isinstance(self.mcc_cmd, str):
            self.errors = 'Versatile Express USB Mass Storage mount command unset'

    def run(self, connection, max_end_time, args=None):
        if not connection:
            raise LAVABug("%s started without a connection already in use" % self.name)
        connection = super(EnableVExpressMassStorage, self).run(connection, max_end_time, args)

        # Issue command and check that you are returned to the prompt again
        connection.sendline('%s\n' % self.mcc_cmd)
        self.logger.debug("Changing prompt to '%s'", self.mcc_prompt)
        connection.prompt_str = self.mcc_prompt
        self.wait(connection)
        return connection


class MountVExpressMassStorageDevice(Action):
    """
    Mounts Versatile Express USB mass storage device on the dispatcher.
    The device is identified by the filesystem label given when running the
    format command on the Versatile Express board.
    """
    def __init__(self):
        super(MountVExpressMassStorageDevice, self).__init__()
        self.name = "mount-vexpress-usbmsd"
        self.description = "mount vexpress usb msd"
        self.summary = "mount vexpress usb mass storage device on the dispatcher"
        self.microsd_fs_label = None

    def validate(self):
        super(MountVExpressMassStorageDevice, self).validate()
        self.microsd_fs_label = self.job.device.get('usb_filesystem_label')
        if not isinstance(self.microsd_fs_label, str):
            self.errors = 'Filesystem label unset for Versatile Express'

    def run(self, connection, max_end_time, args=None):
        connection = super(MountVExpressMassStorageDevice, self).run(connection, max_end_time, args)

        device_path = "/dev/disk/by-label/%s" % self.microsd_fs_label
        try:
            os.path.realpath(device_path)
        except:
            raise InfrastructureError("Unable to find disk by label %s" % device_path)

        mount_point = "/mnt/%s" % self.microsd_fs_label
        mount_cmd = ['mount', device_path, mount_point]
        try:
            self.run_command(mount_cmd)
        except:
            raise InfrastructureError("Failed to mount device %s to %s" % (device_path, mount_point))
        self.set_namespace_data(action=self.name, label='vexpress-fw', key='mount-point', value=mount_point)
        return connection


class DeployVExpressRecoveryImage(Action):
    """
    Removes the current recovery image from the mounted Versatile Express
    USB mass storage device, and copies over the new one
    """
    def __init__(self):
        super(DeployVExpressRecoveryImage, self).__init__()
        self.name = "deploy-vexpress-recovery-image"
        self.description = "deploy vexpress recovery image to usb msd"
        self.summary = "copy recovery image contents to vexpress usb mass storage device"

    def validate(self):
        super(DeployVExpressRecoveryImage, self).validate()
        if not self.valid:
            return

    def run(self, connection, max_end_time, args=None):
        connection = super(DeployVExpressRecoveryImage, self).run(connection, max_end_time, args)
        mount_point = self.get_namespace_data(action='mount-vexpress-usbmsd', label='vexpress-fw', key='mount-point')
        try:
            os.path.realpath(mount_point)
        except OSError:
            raise InfrastructureError("Unable to locate mount point: %s" % mount_point)

        src_dir = self.get_namespace_data(action='extract-vexpress-recovery-image', label='file', key='recovery_image')
        try:
            os.path.realpath(src_dir)
        except OSError:
            raise InfrastructureError("Unable to locate recovery image source directory: %s" % src_dir)

        self.logger.debug("Removing existing recovery image from Versatile Express mass storage device..")
        try:
            remove_directory_contents(mount_point)
        except:
            raise JobError("Failed to erase old recovery image")

        self.logger.debug("Transferring new recovery image to Versatile Express mass storage device..")
        try:
            copy_directory_contents(src_dir, mount_point)
        except:
            raise JobError("Failed to deploy recovery image to %s" % mount_point)
        return connection


class UnmountVExpressMassStorageDevice(Action):
    """
    Unmount Versatile Express USB mass storage device on the dispatcher
    """
    def __init__(self):
        super(UnmountVExpressMassStorageDevice, self).__init__()
        self.name = "unmount-vexpress-usbmsd"
        self.description = "unmount vexpress usb msd"
        self.summary = "unmount vexpress usb mass storage device"

    def run(self, connection, max_end_time, args=None):
        connection = super(UnmountVExpressMassStorageDevice, self).run(connection, max_end_time, args)

        mount_point = self.get_namespace_data(action='mount-vexpress-usbmsd', label='vexpress-fw', key='mount-point')
        try:
            self.run_command(["umount", mount_point])
        except:
            raise JobError("Failed to unmount device %s" % mount_point)
        return connection


class VExpressFlashErase(Action):  # pylint: disable=too-many-instance-attributes
    """
    Enter Versatile Express Flash menu and erase NOR Flash.
    The job writer can define whether this should be a range or all.
    """
    def __init__(self):
        super(VExpressFlashErase, self).__init__()
        self.name = "erase-vexpress-flash"
        self.description = "erase vexpress flash"
        self.summary = "erase vexpress flash using the commands set by the user"
        self.mcc_prompt = None
        self.flash_prompt = None
        self.flash_enter_cmd = None
        self.flash_erase_cmd = None
        self.flash_erase_msg = None
        self.flash_exit_cmd = None

    def validate(self):
        super(VExpressFlashErase, self).validate()
        device_methods = self.job.device['actions']['deploy']['methods']
        self.mcc_prompt = device_methods['vemsd']['parameters'].get('mcc_prompt')
        self.flash_prompt = device_methods['vemsd']['parameters'].get('flash_prompt')
        self.flash_enter_cmd = device_methods['vemsd']['parameters'].get('flash_enter_cmd')
        self.flash_erase_cmd = device_methods['vemsd']['parameters'].get('flash_erase_cmd')
        self.flash_erase_msg = device_methods['vemsd']['parameters'].get('flash_erase_msg')
        self.flash_exit_cmd = device_methods['vemsd']['parameters'].get('flash_exit_cmd')
        if not isinstance(self.mcc_prompt, str):
            self.errors = 'Versatile Express MCC prompt unset'
        if not isinstance(self.flash_prompt, str):
            self.errors = 'Versatile Express flash prompt unset'
        if not isinstance(self.flash_enter_cmd, str):
            self.errors = 'Versatile Express flash enter command unset'
        if not isinstance(self.flash_erase_cmd, str):
            self.errors = 'Versatile Express flash erase command unset'
        if not isinstance(self.flash_erase_msg, str):
            self.errors = 'Versatile Express flash erase message unset'
        if not isinstance(self.flash_exit_cmd, str):
            self.errors = 'Versatile Express flash exit command unset'

    def run(self, connection, max_end_time, args=None):
        if not connection:
            raise RuntimeError("%s started without a connection already in use" % self.name)
        connection = super(VExpressFlashErase, self).run(connection, max_end_time, args)

        # From Versatile Express MCC, enter flash menu
        connection.sendline('%s\n' % self.flash_enter_cmd)
        self.logger.debug("Changing prompt to '%s'", self.flash_prompt)
        connection.prompt_str = self.flash_prompt
        self.wait(connection)

        # Issue flash erase command
        connection.sendline('%s\n' % self.flash_erase_cmd)
        self.logger.debug("Changing prompt to '%s'", self.flash_erase_msg)
        connection.prompt_str = self.flash_erase_msg
        self.wait(connection)

        # Once we know the erase is underway.. wait for the prompt
        self.logger.debug("Changing prompt to '%s'", self.flash_prompt)
        connection.prompt_str = self.flash_prompt
        self.wait(connection)

        # If flash erase command has completed, return to MCC main menu
        connection.sendline('%s\n' % self.flash_exit_cmd)
        self.logger.debug("Changing prompt to '%s'", self.mcc_prompt)
        connection.prompt_str = self.mcc_prompt
        self.wait(connection)
        return connection
