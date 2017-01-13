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

from lava_dispatcher.pipeline.logical import Deployment
from lava_dispatcher.pipeline.connections.serial import ConnectDevice
from lava_dispatcher.pipeline.power import PowerOn
from lava_dispatcher.pipeline.action import (
    Pipeline,
    JobError,
)
from lava_dispatcher.pipeline.actions.deploy import DeployAction
from lava_dispatcher.pipeline.actions.deploy.lxc import LxcAddDeviceAction
from lava_dispatcher.pipeline.actions.deploy.apply_overlay import ApplyOverlaySparseRootfs
from lava_dispatcher.pipeline.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.pipeline.actions.deploy.overlay import (
    CustomisationAction,
    OverlayAction,
)
from lava_dispatcher.pipeline.actions.deploy.download import (
    DownloaderAction,
)
from lava_dispatcher.pipeline.utils.filesystem import copy_to_lxc
from lava_dispatcher.pipeline.protocols.lxc import LxcProtocol
from lava_dispatcher.pipeline.actions.boot import WaitUSBDeviceAction

# pylint: disable=too-many-return-statements


def fastboot_accept(device, parameters):
    """
    Each fastboot deployment strategy uses these checks
    as a base, then makes the final decision on the
    style of fastboot deployment.
    """
    if 'to' not in parameters:
        return False
    if parameters['to'] != 'fastboot':
        return False
    if not device:
        return False
    if 'actions' not in device:
        raise RuntimeError("Invalid device configuration")
    if 'deploy' not in device['actions']:
        return False
    if 'adb_serial_number' not in device:
        return False
    if 'fastboot_serial_number' not in device:
        return False
    if 'methods' not in device['actions']['deploy']:
        raise RuntimeError("Device misconfiguration")
    return True


class Fastboot(Deployment):
    """
    Strategy class for a fastboot deployment.
    Downloads the relevant parts, copies to the locations using fastboot.
    """
    compatibility = 1

    def __init__(self, parent, parameters):
        super(Fastboot, self).__init__(parent)
        self.action = FastbootAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if not fastboot_accept(device, parameters):
            return False
        if 'fastboot' in device['actions']['deploy']['methods']:
            return True
        return False


class FastbootAction(DeployAction):  # pylint:disable=too-many-instance-attributes

    def __init__(self):
        super(FastbootAction, self).__init__()
        self.name = "fastboot-deploy"
        self.description = "download files and deploy using fastboot"
        self.summary = "fastboot deployment"
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

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if self.test_needs_overlay(parameters):
            self.internal_pipeline.add_action(CustomisationAction())
            self.internal_pipeline.add_action(OverlayAction())
        if hasattr(self.job.device, 'power_state'):
            if self.job.device.power_state in ['on', 'off']:
                self.force_prompt = True
                self.internal_pipeline.add_action(ConnectDevice())
                self.internal_pipeline.add_action(PowerOn())
        self.internal_pipeline.add_action(EnterFastbootAction())
        self.internal_pipeline.add_action(WaitUSBDeviceAction(
            device_actions=['add', 'change', 'online']))

        fastboot_dir = self.mkdtemp()
        for image in parameters['images'].keys():
            if image != 'yaml_line':
                download = DownloaderAction(image, fastboot_dir)
                download.max_retries = 3  # overridden by failure_retry in the parameters, if set.
                self.internal_pipeline.add_action(download)
                if image == 'rootfs':
                    if self.test_needs_overlay(parameters):
                        self.internal_pipeline.add_action(
                            ApplyOverlaySparseRootfs())
                    if self.test_needs_deployment(parameters):
                        self.internal_pipeline.add_action(
                            DeployDeviceEnvironment())

        self.internal_pipeline.add_action(LxcAddDeviceAction())
        self.internal_pipeline.add_action(FastbootFlashAction())


class EnterFastbootAction(DeployAction):
    """
    Enters fastboot bootloader.
    """

    def __init__(self):
        super(EnterFastbootAction, self).__init__()
        self.name = "enter_fastboot_action"
        self.description = "enter fastboot bootloader"
        self.summary = "enter fastboot"
        self.retries = 10
        self.sleep = 10

    def validate(self):
        super(EnterFastbootAction, self).validate()
        if 'adb_serial_number' not in self.job.device:
            self.errors = "device adb serial number missing"
            if self.job.device['adb_serial_number'] == '0000000000':
                self.errors = "device adb serial number unset"
        if 'fastboot_serial_number' not in self.job.device:
            self.errors = "device fastboot serial number missing"
            if self.job.device['fastboot_serial_number'] == '0000000000':
                self.errors = "device fastboot serial number unset"

    def run(self, connection, max_end_time, args=None):
        connection = super(EnterFastbootAction, self).run(connection, max_end_time, args)
        # this is the device namespace - the lxc namespace is not accessible
        lxc_name = None
        protocol = [protocol for protocol in self.job.protocols if protocol.name == LxcProtocol.name][0]
        if protocol:
            lxc_name = protocol.lxc_name
        if not lxc_name:
            self.errors = "Unable to use fastboot"
            return connection
        self.logger.debug("[%s] lxc name: %s", self.parameters['namespace'], lxc_name)
        fastboot_serial_number = self.job.device['fastboot_serial_number']

        # Try to enter fastboot mode with adb.
        adb_serial_number = self.job.device['adb_serial_number']
        adb_cmd = ['lxc-attach', '-n', lxc_name, '--', 'adb', '-s',
                   adb_serial_number, 'devices']
        command_output = self.run_command(adb_cmd, allow_fail=True)
        if command_output and adb_serial_number in command_output:
            self.logger.debug("Device is in adb: %s", command_output)
            adb_cmd = ['lxc-attach', '-n', lxc_name, '--', 'adb',
                       '-s', adb_serial_number, 'reboot-bootloader']
            command_output = self.run_command(adb_cmd)
            return connection

        # Enter fastboot mode with fastboot.
        fastboot_cmd = ['lxc-attach', '-n', lxc_name, '--', 'fastboot', '-s',
                        fastboot_serial_number, 'devices']
        command_output = self.run_command(fastboot_cmd)
        if command_output and fastboot_serial_number in command_output:
            self.logger.debug("Device is in fastboot: %s", command_output)
            fastboot_cmd = ['lxc-attach', '-n', lxc_name, '--', 'fastboot',
                            '-s', fastboot_serial_number, 'reboot-bootloader']
            command_output = self.run_command(fastboot_cmd)
            if command_output and 'OKAY' not in command_output:
                raise JobError("Unable to enter fastboot: %s" %
                               command_output)  # FIXME: JobError needs a unit test
            else:
                status = [status.strip() for status in command_output.split(
                    '\n') if 'finished' in status][0]
                self.results = {'status': status}
        return connection


class FastbootFlashAction(DeployAction):
    """
    Fastboot flash image.
    """

    def __init__(self):
        super(FastbootFlashAction, self).__init__()
        self.name = "fastboot_flash_action"
        self.description = "fastboot_flash"
        self.summary = "fastboot flash"
        self.retries = 3
        self.sleep = 10

    def validate(self):
        super(FastbootFlashAction, self).validate()
        if 'fastboot_serial_number' not in self.job.device:
            self.errors = "device fastboot serial number missing"
            if self.job.device['fastboot_serial_number'] == '0000000000':
                self.errors = "device fastboot serial number unset"
        if 'flash_cmds_order' not in self.job.device:
            self.errors = "device flash commands order missing"

    def run(self, connection, max_end_time, args=None):
        connection = super(FastbootFlashAction, self).run(connection, max_end_time, args)
        # this is the device namespace - the lxc namespace is not accessible
        lxc_name = None
        protocol = [protocol for protocol in self.job.protocols if protocol.name == LxcProtocol.name][0]
        if protocol:
            lxc_name = protocol.lxc_name
        if not lxc_name:
            self.errors = "Unable to use fastboot"
            return connection
        # Order flash commands so that some commands take priority over others
        flash_cmds_order = self.job.device['flash_cmds_order']
        namespace = self.parameters.get('namespace', 'common')
        flash_cmds = set(self.data[namespace]['download_action'].keys()).difference(
            set(flash_cmds_order))
        flash_cmds = flash_cmds_order + list(flash_cmds)

        for flash_cmd in flash_cmds:
            src = self.get_namespace_data(action='download_action', label=flash_cmd, key='file')
            if not src:
                continue
            dst = copy_to_lxc(lxc_name, src)
            if flash_cmd in ['boot']:
                continue
            serial_number = self.job.device['fastboot_serial_number']
            fastboot_cmd = ['lxc-attach', '-n', lxc_name, '--', 'fastboot',
                            '-s', serial_number, 'flash', flash_cmd, dst]
            command_output = self.run_command(fastboot_cmd)
            if command_output and 'error' in command_output:
                raise JobError("Unable to flash %s using fastboot: %s",
                               flash_cmd, command_output)  # FIXME: JobError needs a unit test
        return connection
