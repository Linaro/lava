# Copyright (C) 2015 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
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

from lava_dispatcher.logical import Deployment
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.power import (
    ResetDevice,
)
from lava_dispatcher.action import (
    InfrastructureError,
    JobError,
    Pipeline,
    Action,
)
from lava_dispatcher.actions.deploy import DeployAction
from lava_dispatcher.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.actions.deploy.apply_overlay import (
    ApplyOverlaySparseImage,
    ApplyOverlayImage,
)
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.utils.filesystem import copy_to_lxc
from lava_dispatcher.protocols.lxc import LxcProtocol
from lava_dispatcher.actions.boot.fastboot import EnterFastbootAction
from lava_dispatcher.actions.boot.u_boot import UBootEnterFastbootAction
from lava_dispatcher.power import PDUReboot, ReadFeedback


# pylint: disable=too-many-return-statements,too-many-instance-attributes,missing-docstring


class Fastboot(Deployment):
    """
    Strategy class for a fastboot deployment.
    Downloads the relevant parts, copies to the locations using fastboot.
    """
    compatibility = 1
    name = 'fastboot'

    def __init__(self, parent, parameters):
        super(Fastboot, self).__init__(parent)
        self.action = FastbootAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if 'to' not in parameters:
            return False, '"to" is not in deploy parameters'
        if parameters['to'] != 'fastboot':
            return False, '"to" parameter is not "fastboot"'
        if 'deploy' not in device['actions']:
            return False, '"deploy" is not in the device configuration actions'
        if 'adb_serial_number' not in device:
            return False, '"adb_serial_number" is not in the device configuration'
        if 'fastboot_serial_number' not in device:
            return False, '"fastboot_serial_number" is not in the device configuration'
        if 'fastboot_options' not in device:
            return False, '"fastboot_options" is not in the device configuration'
        if 'fastboot' in device['actions']['deploy']['methods']:
            return True, 'accepted'
        return False, '"fastboot" was not in the device configuration deploy methods"'


class FastbootAction(DeployAction):  # pylint:disable=too-many-instance-attributes

    name = "fastboot-deploy"
    description = "download files and deploy using fastboot"
    summary = "fastboot deployment"

    def __init__(self):
        super(FastbootAction, self).__init__()
        self.force_prompt = False

    def validate(self):
        super(FastbootAction, self).validate()
        if not self.test_needs_deployment(self.parameters):
            return
        lava_test_results_dir = self.parameters['deployment_data']['lava_test_results_dir']
        lava_test_results_dir = lava_test_results_dir % self.job.job_id
        self.set_namespace_data(action='test', label='results', key='lava_test_results_dir', value=lava_test_results_dir)
        lava_test_sh_cmd = self.parameters['deployment_data']['lava_test_sh_cmd']
        self.set_namespace_data(action=self.name, label='shared', key='lava_test_sh_cmd', value=lava_test_sh_cmd)
        protocol = [protocol for protocol in self.job.protocols if protocol.name == LxcProtocol.name]
        if not protocol:
            self.errors = "No LXC device requested"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if self.test_needs_overlay(parameters):
            self.internal_pipeline.add_action(OverlayAction())
        # Check if the device has a power command such as HiKey, Dragonboard,
        # etc. against device that doesn't like Nexus, etc.
        if self.job.device.get('fastboot_via_uboot', False):
            self.internal_pipeline.add_action(ConnectDevice())
            self.internal_pipeline.add_action(UBootEnterFastbootAction())
        elif self.job.device.power_command:
            self.force_prompt = True
            self.internal_pipeline.add_action(ConnectDevice())
            self.internal_pipeline.add_action(ResetDevice())
        else:
            self.internal_pipeline.add_action(EnterFastbootAction())

        fastboot_dir = self.mkdtemp()
        image_keys = sorted(parameters['images'].keys())
        for image in image_keys:
            if image != 'yaml_line':
                self.internal_pipeline.add_action(DownloaderAction(image, fastboot_dir))
                if parameters['images'][image].get('apply-overlay', False):
                    if self.test_needs_overlay(parameters):
                        if parameters['images'][image].get('sparse', True):
                            self.internal_pipeline.add_action(
                                ApplyOverlaySparseImage(image))
                        else:
                            self.internal_pipeline.add_action(
                                ApplyOverlayImage(image, use_root_partition=False))
                if self.test_needs_overlay(parameters) and \
                   self.test_needs_deployment(parameters):
                    self.internal_pipeline.add_action(
                        DeployDeviceEnvironment())
        self.internal_pipeline.add_action(FastbootFlashOrderAction())


class FastbootFlashOrderAction(DeployAction):
    """
    Fastboot flash image.
    """

    name = "fastboot-flash-order-action"
    description = "Determine support for each flash operation"
    summary = "Handle reset and options for each flash url."

    def __init__(self):
        super(FastbootFlashOrderAction, self).__init__()
        self.retries = 3
        self.sleep = 10
        self.interrupt_prompt = None
        self.interrupt_string = None
        self.reboot = None

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        flash_cmds_order = self.job.device['flash_cmds_order']
        userlist = list(parameters['images'].keys())
        userlist.remove('yaml_line')
        flash_cmds = set(userlist).difference(set(flash_cmds_order))
        flash_cmds = flash_cmds_order + list(flash_cmds)
        self.internal_pipeline.add_action(ReadFeedback(repeat=True))
        for flash_cmd in flash_cmds:
            if flash_cmd not in parameters['images']:
                continue
            self.internal_pipeline.add_action(FastbootFlashAction(cmd=flash_cmd))
            self.reboot = parameters['images'][flash_cmd].get('reboot', None)
            if self.reboot == 'fastboot-reboot':
                self.internal_pipeline.add_action(FastbootReboot())
                self.internal_pipeline.add_action(ReadFeedback(repeat=True))
            elif self.reboot == 'fastboot-reboot-bootloader':
                self.internal_pipeline.add_action(FastbootRebootBootloader())
                self.internal_pipeline.add_action(ReadFeedback(repeat=True))
            elif self.reboot == 'hard-reset':
                self.internal_pipeline.add_action(PDUReboot())
                self.internal_pipeline.add_action(ReadFeedback(repeat=True))

    def validate(self):
        super(FastbootFlashOrderAction, self).validate()
        self.set_namespace_data(
            action=FastbootFlashAction.name, label='interrupt',
            key='reboot', value=self.reboot)
        if 'fastboot_serial_number' not in self.job.device:
            self.errors = "device fastboot serial number missing"
        elif self.job.device['fastboot_serial_number'] == '0000000000':
            self.errors = "device fastboot serial number unset"
        if 'flash_cmds_order' not in self.job.device:
            self.errors = "device flash commands order missing"
        if 'fastboot_options' not in self.job.device:
            self.errors = "device fastboot options missing"
        elif not isinstance(self.job.device['fastboot_options'], list):
            self.errors = "device fastboot options is not a list"


class FastbootFlashAction(Action):

    """
    Fastboot flash image.
    """

    name = "fastboot-flash-action"
    description = "Run a specified flash command"
    summary = "Execute fastboot flash command"

    def __init__(self, cmd=None):
        super(FastbootFlashAction, self).__init__()
        self.retries = 3
        self.sleep = 10
        self.command = cmd
        self.interrupt_prompt = None
        self.interrupt_string = None

    def validate(self):
        super(FastbootFlashAction, self).validate()
        if not self.command:
            self.errors = "Invalid configuration - missing flash command"
        device_methods = self.job.device['actions']['deploy']['methods']
        if isinstance(device_methods.get('fastboot'), dict):
            self.interrupt_prompt = device_methods['fastboot'].get('interrupt_prompt')
            self.interrupt_string = device_methods['fastboot'].get('interrupt_string')

    def run(self, connection, max_end_time, args=None):  # pylint: disable=too-many-locals
        connection = super(FastbootFlashAction, self).run(connection, max_end_time, args)
        # this is the device namespace - the lxc namespace is not accessible
        lxc_name = None
        protocol = [protocol for protocol in self.job.protocols if protocol.name == LxcProtocol.name][0]
        if protocol:
            lxc_name = protocol.lxc_name
        if not lxc_name:
            raise JobError("Unable to use fastboot")

        src = self.get_namespace_data(action='download-action', label=self.command, key='file')
        if not src:
            return connection
        dst = copy_to_lxc(lxc_name, src, self.job.parameters['dispatcher'])
        sequence = self.job.device['actions']['boot']['methods'].get(
            'fastboot', [])
        if 'no-flash-boot' in sequence and self.command in ['boot']:
            return connection

        # if a reboot is requested, will need to wait for the prompt
        # if not, continue in the existing mode.
        reboot = self.get_namespace_data(
            action=self.name, label='interrupt', key='reboot')
        if self.interrupt_prompt and reboot:
            connection.prompt_str = self.interrupt_prompt
            self.logger.debug("Changing prompt to '%s'", connection.prompt_str)
            self.wait(connection)

        serial_number = self.job.device['fastboot_serial_number']
        fastboot_opts = self.job.device['fastboot_options']
        fastboot_cmd = ['lxc-attach', '-n', lxc_name, '--', 'fastboot',
                        '-s', serial_number, 'flash', self.command,
                        dst] + fastboot_opts
        self.logger.info("Handling %s", self.command)
        command_output = self.run_command(fastboot_cmd)
        if command_output and 'error' in command_output:
            raise InfrastructureError("Unable to flash %s using fastboot: %s" %
                                      (self.command, command_output))
        self.results = {'label': self.command}

        return connection


class FastbootReboot(Action):

    name = 'fastboot-reboot'
    description = 'Reset a device between flash operations using fastboot reboot.'
    summary = 'execute a reboot using fastboot'

    def run(self, connection, max_end_time, args=None):  # pylint: disable=too-many-locals

        connection = super(FastbootReboot, self).run(connection, max_end_time, args)
        # this is the device namespace - the lxc namespace is not accessible
        lxc_name = None
        protocol = [protocol for protocol in self.job.protocols if protocol.name == LxcProtocol.name][0]
        if protocol:
            lxc_name = protocol.lxc_name
        if not lxc_name:
            raise JobError("Unable to use fastboot")

        serial_number = self.job.device['fastboot_serial_number']
        fastboot_opts = self.job.device['fastboot_options']

        self.logger.info("fastboot rebooting device.")
        fastboot_cmd = ['lxc-attach', '-n', lxc_name, '--',
                        'fastboot', '-s', serial_number,
                        'reboot'] + fastboot_opts
        command_output = self.run_command(fastboot_cmd)
        if command_output and 'error' in command_output:
            raise InfrastructureError("Unable to reboot: %s"
                                      % (command_output))
        return connection


class FastbootRebootBootloader(Action):

    name = 'fastboot-reboot-bootloader'
    description = 'Reset a device between flash operations using fastboot reboot-bootloader.'
    summary = 'execute a reboot to bootloader using fastboot'

    def run(self, connection, max_end_time, args=None):  # pylint: disable=too-many-locals

        connection = super(FastbootRebootBootloader, self).run(connection, max_end_time, args)
        # this is the device namespace - the lxc namespace is not accessible
        lxc_name = None
        protocol = [protocol for protocol in self.job.protocols if protocol.name == LxcProtocol.name][0]
        if protocol:
            lxc_name = protocol.lxc_name
        if not lxc_name:
            raise JobError("Unable to use fastboot")

        serial_number = self.job.device['fastboot_serial_number']
        fastboot_opts = self.job.device['fastboot_options']

        self.logger.info("fastboot reboot device to bootloader.")
        fastboot_cmd = ['lxc-attach', '-n', lxc_name, '--',
                        'fastboot', '-s', serial_number,
                        'reboot-bootloader'] + fastboot_opts
        command_output = self.run_command(fastboot_cmd)
        if command_output and 'error' in command_output:
            raise InfrastructureError(
                "Unable to reboot to bootloader: %s"
                % (command_output))
        return connection
