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
from lava_common.exceptions import ConfigurationError
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.boot import (
    AutoLoginAction,
    BootloaderCommandOverlay,
    BootloaderCommandsAction,
    BootHasMixin,
    OverlayUnpack,
)
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.logical import Boot, RetryAction
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

    @classmethod
    def action(cls):
        return DepthchargeAction()

    @classmethod
    def accepts(cls, device, parameters):
        if parameters["method"] != "depthcharge":
            return False, '"method" was not "depthcharge"'
        if "commands" not in parameters:
            raise ConfigurationError("commands not specified in boot parameters")
        if "depthcharge" not in device["actions"]["boot"]["methods"]:
            return (
                False,
                '"depthcharge" was not in the device configuration boot methods',
            )
        return True, "accepted"


class DepthchargeCommandOverlay(BootloaderCommandOverlay):
    """
    Create the cmdline file and substitute {CMDLINE} with the TFTP path.
    """

    name = "depthcharge-overlay"

    def __init__(self):
        super().__init__()
        self.cmdline = None

    def validate(self):
        super().validate()
        method = self.job.device["actions"]["boot"]["methods"][self.method]
        commands_name = self.parameters["commands"]
        method_params = method[commands_name]
        self.cmdline = method_params.get("cmdline")
        if self.cmdline is None:
            self.errors = "No cmdline found in {}".format(commands_name)

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)

        # Create the cmdline file, this is not set by any bootloader command
        ip_addr = dispatcher_ip(self.job.parameters["dispatcher"], "nfs")
        kernel_path = self.get_namespace_data(
            action="download-action", label="kernel", key="file"
        )
        cmdline_path = os.path.join(os.path.dirname(kernel_path), "cmdline")
        nfs_address = self.get_namespace_data(
            action="persistent-nfs-overlay", label="nfs_address", key="nfsroot"
        )
        nfs_root = self.get_namespace_data(
            action="download-action", label="file", key="nfsrootfs"
        )

        if nfs_root:
            substitutions = {
                "{NFSROOTFS}": self.get_namespace_data(
                    action="extract-rootfs", label="file", key="nfsroot"
                ),
                "{NFS_SERVER_IP}": ip_addr,
            }
        elif nfs_address:
            substitutions = {
                "{NFSROOTFS}": nfs_address,
                "{NFS_SERVER_IP}": self.get_namespace_data(
                    action="persistent-nfs-overlay", label="nfs_address", key="serverip"
                ),
            }
        else:
            substitutions = {}
        cmdline = substitute([self.cmdline], substitutions)[0]

        with open(cmdline_path, "w") as cmdline_file:
            cmdline_file.write(cmdline)

        # Substitute {CMDLINE} with the cmdline file TFTP path
        kernel_tftp = self.get_namespace_data(
            action="download-action", label="file", key="kernel"
        )
        cmdline_tftp = os.path.join(os.path.dirname(kernel_tftp), "cmdline")
        fit_tftp = self.get_namespace_data(
            action="prepare-fit", label="file", key="fit"
        )
        substitutions = {"{CMDLINE}": cmdline_tftp, "{FIT}": fit_tftp}
        commands = self.get_namespace_data(
            action="bootloader-overlay", label=self.method, key="commands"
        )
        commands = substitute(commands, substitutions)
        self.set_namespace_data(
            action="bootloader-overlay",
            label=self.method,
            key="commands",
            value=commands,
        )
        self.logger.info("Parsed boot commands: %s", "; ".join(commands))

        return connection


class DepthchargeAction(Action):
    """
    Wraps the Retry Action to allow for actions which precede the reset,
    e.g. Connect.
    """

    name = "depthcharge-action"
    description = "interactive Depthcharge action"
    summary = "sets up boot with Depthcharge"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(DepthchargeCommandOverlay())
        self.pipeline.add_action(ConnectDevice())
        self.pipeline.add_action(DepthchargeRetry())


class DepthchargeRetry(BootHasMixin, RetryAction):

    name = "depthcharge-retry"
    description = "interactive depthcharge retry action"
    summary = "depthcharge commands with retry"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(ResetDevice())
        self.pipeline.add_action(DepthchargeStart())
        self.pipeline.add_action(BootloaderCommandsAction())
        if self.has_prompts(parameters):
            self.pipeline.add_action(AutoLoginAction())
            if self.test_has_shell(parameters):
                self.pipeline.add_action(ExpectShellSession())
                if "transfer_overlay" in parameters:
                    self.pipeline.add_action(OverlayUnpack())
                self.pipeline.add_action(ExportDeviceEnvironment())


class DepthchargeStart(Action):
    """
    Wait for the Depthcharge command line interface prompt.
    """

    name = "depthcharge-start"
    description = "wait for Depthcharge to start"
    summary = "Depthcharge start"

    def __init__(self):
        super().__init__()
        self.start_message = None

    def validate(self):
        super().validate()
        if self.job.device.connect_command == "":
            self.errors = "Unable to connect to device"
        method = self.job.device["actions"]["boot"]["methods"]["depthcharge"]
        self.start_message = method["parameters"].get("start_message")
        if self.start_message is None:
            self.errors = "Missing Depthcharge start message for device"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        connection.prompt_str = self.start_message
        self.logger.debug("Changing prompt to '%s'", connection.prompt_str)
        self.wait(connection)
        return connection
