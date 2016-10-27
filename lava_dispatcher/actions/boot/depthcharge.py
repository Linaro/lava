# Copyright (C) 2016, 2017 Collabora Ltd.
#
# Author: Tomeu Vizoso <tomeu.vizoso@collabora.com>
# Author: Guillaume Tucker <guillaume.tucker@collabora.com>
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


import os.path
from lava_dispatcher.action import (
    Action,
    ConfigurationError,
    Pipeline,
)
from lava_dispatcher.actions.boot import (
    AutoLoginAction,
    BootAction,
    BootloaderCommandOverlay,
    BootloaderCommandsAction,
    OverlayUnpack,
)
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.logical import Boot
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.shell import ExpectShellSession
from lava_dispatcher.utils.strings import substitute
from lava_dispatcher.utils.network import dispatcher_ip


class Depthcharge(Boot):
    """
    Depthcharge is a payload used by Coreboot in recent ChromeOS machines.
    This boot strategy works with the "netboot" build variant of Depthcharge,
    which just downloads files via TFTP from hardcoded locations, with the IP
    address of the server also hardcoded in the firmware image. One of the
    downloaded files is a FIT image that contains the kernel, ramdisk and
    device tree blob, and the other contains the kernel arguments.
    """
    def __init__(self, parent, parameters):
        super(Depthcharge, self).__init__(parent)
        self.action = DepthchargeAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if parameters['method'] != 'depthcharge':
            return False, '"method" was not "depthcharge"'
        if 'commands' not in parameters:
            raise ConfigurationError(
                "commands not specified in boot parameters")
        if 'depthcharge' not in device['actions']['boot']['methods']:
            return (
                False,
                '"depthcharge" was not in the device configuration boot methods'
            )
        return True, 'accepted'


class DepthchargeCommandOverlay(BootloaderCommandOverlay):
    """
    Create the cmdline file and substitute {CMDLINE} with the TFTP path.
    """
    def __init__(self):
        super(DepthchargeCommandOverlay, self).__init__()
        self.name = "depthcharge-overlay"
        self.cmdline = None

    def validate(self):
        super(DepthchargeCommandOverlay, self).validate()
        method = self.job.device['actions']['boot']['methods'][self.method]
        commands_name = self.parameters['commands']
        method_params = method[commands_name]
        self.cmdline = method_params.get('cmdline')
        if self.cmdline is None:
            self.errors = "No cmdline found in {}".format(commands_name)

    def run(self, connection, max_end_time, args=None):
        connection = super(DepthchargeCommandOverlay, self).run(
            connection, max_end_time, args)

        # Create the cmdline file, this is not set by any bootloader commands
        ip_addr = dispatcher_ip(self.job.parameters['dispatcher'])
        kernel_path = self.get_namespace_data(
            action='download-action', label='kernel', key='file')
        cmdline_path = os.path.join(os.path.dirname(kernel_path), 'cmdline')
        nfs_address = self.get_namespace_data(
            action='persistent-nfs-overlay', label='nfs_address', key='nfsroot')
        nfs_root = self.get_namespace_data(
            action='download-action', label='file', key='nfsrootfs')

        if nfs_root:
            substitutions = {
                '{NFSROOTFS}': self.get_namespace_data(
                    action='extract-rootfs', label='file', key='nfsroot'),
                '{NFS_SERVER_IP}': ip_addr,
            }
        elif nfs_address:
            substitutions = {
                '{NFSROOTFS}': nfs_address,
                '{NFS_SERVER_IP}': self.get_namespace_data(
                    action='persistent-nfs-overlay', label='nfs_address',
                    key='serverip'),
            }
        else:
            substitutions = {}
        cmdline = substitute([self.cmdline], substitutions)[0]

        with open(cmdline_path, "w") as cmdline_file:
            cmdline_file.write(cmdline)

        # Substitute {CMDLINE} with the cmdline file TFTP path
        kernel_tftp = self.get_namespace_data(
            action='download-action', label='file', key='kernel')
        cmdline_tftp = os.path.join(os.path.dirname(kernel_tftp), 'cmdline')
        substitutions = {
            '{CMDLINE}': cmdline_tftp,
        }
        commands = self.get_namespace_data(
            action='bootloader-overlay', label=self.method, key='commands')
        commands = substitute(commands, substitutions)
        self.set_namespace_data(
            action='bootloader-overlay', label=self.method, key='commands',
            value=commands)
        self.logger.info("Parsed boot commands: %s", '; '.join(commands))

        return connection


class DepthchargeAction(BootAction):
    """
    Wraps the Retry Action to allow for actions which precede the reset,
    e.g. Connect.
    """
    def __init__(self):
        super(DepthchargeAction, self).__init__()
        self.name = "depthcharge-action"
        self.description = "interactive Depthcharge action"
        self.summary = "sets up boot with Depthcharge"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(
            parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(DepthchargeCommandOverlay())
        self.internal_pipeline.add_action(ConnectDevice())
        self.internal_pipeline.add_action(DepthchargeRetry())


class DepthchargeRetry(BootAction):

    def __init__(self):
        super(DepthchargeRetry, self).__init__()
        self.name = "depthcharge-retry"
        self.description = "interactive depthcharge retry action"
        self.summary = "depthcharge commands with retry"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(
            parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(ResetDevice())
        self.internal_pipeline.add_action(DepthchargeStart())
        self.internal_pipeline.add_action(BootloaderCommandsAction())
        if self.has_prompts(parameters):
            self.internal_pipeline.add_action(AutoLoginAction())
            if self.test_has_shell(parameters):
                self.internal_pipeline.add_action(ExpectShellSession())
                if 'transfer_overlay' in parameters:
                    self.internal_pipeline.add_action(OverlayUnpack())
                self.internal_pipeline.add_action(ExportDeviceEnvironment())

    def run(self, connection, max_end_time, args=None):
        connection = super(DepthchargeRetry, self).run(
            connection, max_end_time, args)
        self.set_namespace_data(
            action='shared', label='shared', key='connection', value=connection)
        return connection


class DepthchargeStart(Action):
    """
    Wait for the Depthcharge command line interface prompt.
    """
    def __init__(self):
        super(DepthchargeStart, self).__init__()
        self.name = "depthcharge-start"
        self.description = "wait for Depthcharge to start"
        self.summary = "Depthcharge start"
        self.start_message = None

    def validate(self):
        super(DepthchargeStart, self).validate()
        if self.job.device.connect_command is '':
            self.errors = "Unable to connect to device %s"
        method = self.job.device['actions']['boot']['methods']['depthcharge']
        self.start_message = method['parameters'].get('start_message')
        if self.start_message is None:
            self.errors = "Missing Depthcharge start message for device"

    def run(self, connection, max_end_time, args=None):
        connection = super(DepthchargeStart, self).run(
            connection, max_end_time, args)
        connection.prompt_str = self.start_message
        self.logger.debug("Changing prompt to '%s'", connection.prompt_str)
        self.wait(connection)
        return connection
