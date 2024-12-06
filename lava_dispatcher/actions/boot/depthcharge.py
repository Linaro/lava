# Copyright (C) 2016, 2017 Collabora Ltd.
#
# Author: Tomeu Vizoso <tomeu.vizoso@collabora.com>
# Author: Guillaume Tucker <guillaume.tucker@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import os.path
from typing import TYPE_CHECKING

from lava_common.constants import BOOTLOADER_DEFAULT_CMD_TIMEOUT
from lava_common.exceptions import InfrastructureError
from lava_common.timeout import Timeout
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.boot import (
    AutoLoginAction,
    BootHasMixin,
    BootloaderCommandOverlay,
    BootloaderCommandsAction,
    OverlayUnpack,
)
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.connections.serial import ResetConnection
from lava_dispatcher.logical import RetryAction
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.shell import ExpectShellSession
from lava_dispatcher.utils.network import dispatcher_ip
from lava_dispatcher.utils.strings import substitute

if TYPE_CHECKING:
    from lava_dispatcher.job import Job


class DepthchargeCommandOverlay(BootloaderCommandOverlay):
    """
    Create the cmdline file and substitute {CMDLINE} with the TFTP path.
    """

    name = "depthcharge-overlay"

    def __init__(self, job: Job):
        super().__init__(job)
        self.cmdline = None

    def validate(self):
        super().validate()
        method = self.job.device["actions"]["boot"]["methods"][self.method]
        commands_name = self.parameters["commands"]
        method_params = method[commands_name]
        self.cmdline = method_params.get("cmdline")
        if self.cmdline is None:
            self.errors = f"No cmdline found in {commands_name}"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)

        # Create the cmdline file, this is not set by any bootloader command
        ip_addr = dispatcher_ip(self.job.parameters["dispatcher"], "nfs")
        kernel_path = self.get_namespace_data(
            action="download-action", label="kernel", key="file"
        )
        cmdline_path = os.path.join(os.path.dirname(kernel_path), "cmdline")
        nfs_address = self.get_namespace_data(
            action="parse-persistent-nfs", label="nfs_address", key="nfsroot"
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
                    action="parse-persistent-nfs", label="nfs_address", key="serverip"
                ),
            }
        else:
            substitutions = {}
        cmdline = substitute([self.cmdline], substitutions)[0]

        if "extra_kernel_args" in self.parameters:
            cmdline = " ".join([cmdline, self.parameters["extra_kernel_args"]])

        with open(cmdline_path, "w") as cmdline_file:
            cmdline_file.write(cmdline)

        # Substitute {CMDLINE} with the cmdline file TFTP path
        kernel_tftp = self.get_namespace_data(
            action="download-action", label="file", key="kernel"
        )
        cmdline_tftp = os.path.join(os.path.dirname(kernel_tftp), "cmdline")

        # Load FIT image if available, otherwise plain kernel image
        fit_tftp = self.get_namespace_data(
            action="prepare-fit", label="file", key="fit"
        )

        # Also load ramdisk if available and not using a FIT image
        ramdisk_tftp = self.get_namespace_data(
            action="compress-ramdisk", label="file", key="ramdisk"
        )

        substitutions = {
            "{CMDLINE}": cmdline_tftp,
            "{DEPTHCHARGE_KERNEL}": fit_tftp or kernel_tftp,
            "{DEPTHCHARGE_RAMDISK}": ramdisk_tftp or "" if not fit_tftp else "",
        }
        commands = self.get_namespace_data(
            action="bootloader-overlay", label=self.method, key="commands"
        )
        commands = substitute(commands, substitutions, drop=True, drop_line=False)
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
        self.pipeline.add_action(DepthchargeCommandOverlay(self.job))
        self.pipeline.add_action(DepthchargeRetry(self.job))


class DepthchargeRetry(BootHasMixin, RetryAction):
    name = "depthcharge-retry"
    description = "interactive depthcharge retry action"
    summary = "depthcharge commands with retry"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.pipeline.add_action(ResetConnection(self.job))
        self.pipeline.add_action(ResetDevice(self.job))
        self.pipeline.add_action(DepthchargeStart(self.job))
        self.pipeline.add_action(BootloaderCommandsAction(self.job))
        if self.has_prompts(parameters):
            self.pipeline.add_action(AutoLoginAction(self.job))
            if self.test_has_shell(parameters):
                self.pipeline.add_action(ExpectShellSession(self.job))
                if "transfer_overlay" in parameters:
                    self.pipeline.add_action(OverlayUnpack(self.job))
                self.pipeline.add_action(ExportDeviceEnvironment(self.job))


class DepthchargeStart(Action):
    """
    Wait for the Depthcharge command line interface prompt.
    """

    name = "depthcharge-start"
    description = "wait for Depthcharge to start"
    summary = "Depthcharge start"
    timeout_exception = InfrastructureError

    def __init__(self, job: Job):
        super().__init__(job)
        self.start_message = None
        self.timeout = Timeout(
            self.name,
            self,
            duration=BOOTLOADER_DEFAULT_CMD_TIMEOUT,
            exception=self.timeout_exception,
        )

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
