# Copyright (C) 2015-2018 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import shlex

from lava_common.exceptions import InfrastructureError, JobError, LAVABug
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.boot import (
    AdbOverlayUnpack,
    AutoLoginAction,
    BootHasMixin,
    OverlayUnpack,
)
from lava_dispatcher.actions.boot.environment import ExportDeviceEnvironment
from lava_dispatcher.actions.boot.u_boot import UBootEnterFastbootAction
from lava_dispatcher.connections.adb import ConnectAdb
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.logical import Boot, RetryAction
from lava_dispatcher.power import PreOs, ResetDevice
from lava_dispatcher.shell import ExpectShellSession
from lava_dispatcher.utils.adb import OptionalContainerAdbAction
from lava_dispatcher.utils.fastboot import OptionalContainerFastbootAction
from lava_dispatcher.utils.udev import WaitDeviceBoardID


def _fastboot_sequence_map(sequence):
    """Maps fastboot sequence with corresponding class."""
    sequence_map = {
        "boot": (FastbootBootAction, None),
        "reboot": (FastbootRebootAction, None),
        "no-flash-boot": (FastbootBootAction, None),
        "auto-login": (AutoLoginAction, None),
        "overlay-unpack": (OverlayUnpack, None),
        "shell-session": (ExpectShellSession, None),
        "export-env": (ExportDeviceEnvironment, None),
    }
    return sequence_map.get(sequence, (None, None))


class BootFastboot(Boot):
    """
    Expects fastboot bootloader, and boots.
    """

    @classmethod
    def action(cls):
        return BootFastbootAction()

    @classmethod
    def accepts(cls, device, parameters):
        if parameters["method"] != "fastboot":
            return False, 'boot "method" was not "fastboot"'

        return True, "accepted"


class BootFastbootCommands(OptionalContainerFastbootAction):
    name = "fastboot-boot-commands"
    description = "Run custom fastboot commands before boot"
    summary = "Run fastboot boot commands"
    timeout_exception = InfrastructureError

    def run(self, connection, max_end_time):
        serial_number = self.job.device["fastboot_serial_number"]
        self.logger.info("Running custom fastboot boot commands....")
        for command in self.parameters.get("commands"):
            self.run_fastboot(shlex.split(command))


class BootFastbootAction(BootHasMixin, RetryAction, OptionalContainerFastbootAction):
    """
    Provide for auto_login parameters in this boot stanza and re-establish the
    connection after boot.
    """

    name = "fastboot-boot"
    description = "fastboot boot into the system"
    summary = "fastboot boot"

    def validate(self):
        super().validate()
        sequences = self.job.device["actions"]["boot"]["methods"].get("fastboot", [])
        if sequences is not None:
            for sequence in sequences:
                if not _fastboot_sequence_map(sequence):
                    self.errors = "Unknown boot sequence '%s'" % sequence
        else:
            self.errors = "fastboot_sequence undefined"

    def populate(self, parameters):
        self.parameters = parameters
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)

        if parameters.get("commands"):
            self.pipeline.add_action(BootFastbootCommands())

        board_id = self.job.device["fastboot_serial_number"]

        # Always ensure the device is in fastboot mode before trying to boot.
        # Check if the device has a power command such as HiKey, Dragonboard,
        # etc. against device that doesn't like Nexus, etc.
        if self.job.device.get("fastboot_via_uboot", False):
            self.pipeline.add_action(ConnectDevice())
            self.pipeline.add_action(UBootEnterFastbootAction())
        elif self.job.device.hard_reset_command:
            self.force_prompt = True
            self.pipeline.add_action(ConnectDevice())
            self.pipeline.add_action(ResetDevice())
        else:
            self.pipeline.add_action(WaitDeviceBoardID(board_id))
            self.pipeline.add_action(EnterFastbootAction())

        # Based on the boot sequence defined in the device configuration, add
        # the required pipeline actions.
        sequences = self.job.device["actions"]["boot"]["methods"].get("fastboot", [])
        for sequence in sequences:
            mapped = _fastboot_sequence_map(sequence)
            self.pipeline.add_action(WaitDeviceBoardID(board_id))
            if mapped[1]:
                self.pipeline.add_action(mapped[0](device_actions=mapped[1]))
            elif mapped[0]:
                self.pipeline.add_action(mapped[0]())
        if self.job.device.hard_reset_command:
            if not self.is_container():
                self.pipeline.add_action(PreOs())
            if self.has_prompts(parameters):
                self.pipeline.add_action(AutoLoginAction())
                if self.test_has_shell(parameters):
                    self.pipeline.add_action(ExpectShellSession())
                    if "transfer_overlay" in parameters:
                        self.pipeline.add_action(OverlayUnpack())
                    self.pipeline.add_action(ExportDeviceEnvironment())
        else:
            if not self.is_container():
                self.pipeline.add_action(ConnectAdb())
                self.pipeline.add_action(AdbOverlayUnpack())


class WaitFastBootInterrupt(Action):
    """
    Interrupts fastboot to access the next bootloader
    Relies on fastboot-flash-action setting the prompt and string
    from the deployment parameters.
    """

    name = "wait-fastboot-interrupt"
    description = "Check for prompt and pass the interrupt string to exit fastboot."
    summary = "watch output and try to interrupt fastboot"

    def __init__(self, itype):
        super().__init__()
        self.type = itype
        self.prompt = None
        self.string = None

    def validate(self):
        super().validate()
        if "fastboot_serial_number" not in self.job.device:
            self.errors = "device fastboot serial number missing"
        elif self.job.device["fastboot_serial_number"] == "0000000000":
            self.errors = "device fastboot serial number unset"
        if "fastboot_options" not in self.job.device:
            self.errors = "device fastboot options missing"
        elif not isinstance(self.job.device["fastboot_options"], list):
            self.errors = "device fastboot options is not a list"
        device_methods = self.job.device["actions"]["deploy"]["methods"]
        if isinstance(device_methods.get("fastboot"), dict):
            self.prompt = device_methods["fastboot"].get("interrupt_prompt")
            self.string = device_methods["fastboot"].get("interrupt_string")
        if not self.prompt or not self.string:
            self.errors = "Missing interrupt configuration for device."

    def run(self, connection, max_end_time):
        if not connection:
            raise LAVABug("%s started without a connection already in use" % self.name)
        connection = super().run(connection, max_end_time)
        # device is to be put into a reset state, either by issuing 'reboot' or power-cycle
        connection.prompt_str = self.prompt
        self.logger.debug("Changing prompt to '%s'", connection.prompt_str)
        self.wait(connection)
        self.logger.debug("Sending '%s' to interrupt fastboot.", self.string)
        connection.sendline(self.string)
        return connection


class FastbootBootAction(OptionalContainerFastbootAction):
    """
    This action calls fastboot to boot into the system.
    """

    name = "boot-fastboot"
    description = "fastboot boot into system"
    summary = "attempt to fastboot boot"

    def validate(self):
        super().validate()
        if "fastboot_serial_number" not in self.job.device:
            self.errors = "device fastboot serial number missing"
        elif self.job.device["fastboot_serial_number"] == "0000000000":
            self.errors = "device fastboot serial number unset"
        if "fastboot_options" not in self.job.device:
            self.errors = "device fastboot options missing"
        elif not isinstance(self.job.device["fastboot_options"], list):
            self.errors = "device fastboot options is not a list"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)

        boot_img = self.get_namespace_data(
            action="download-action", label="boot", key="file"
        )
        boot_img = self.maybe_copy_to_container(boot_img)

        command_output = self.get_fastboot_output(["boot", boot_img], allow_fail=True)
        if command_output and "booting" not in command_output.lower():
            raise JobError("Unable to boot with fastboot: %s" % command_output)
        else:
            lines = [
                status
                for status in command_output.split("\n")
                if "finished" in status.lower()
            ]
            if lines:
                self.results = {"status": lines[0].strip()}
            else:
                self.results = {"fail": self.name}
        return connection


class FastbootRebootAction(OptionalContainerFastbootAction):
    """
    This action calls fastboot to reboot into the system.
    """

    name = "fastboot-reboot"
    description = "fastboot reboot into system"
    summary = "attempt to fastboot reboot"

    def validate(self):
        super().validate()
        if "fastboot_serial_number" not in self.job.device:
            self.errors = "device fastboot serial number missing"
        elif self.job.device["fastboot_serial_number"] == "0000000000":
            self.errors = "device fastboot serial number unset"
        if "fastboot_options" not in self.job.device:
            self.errors = "device fastboot options missing"
        elif not isinstance(self.job.device["fastboot_options"], list):
            self.errors = "device fastboot options is not a list"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        command_output = self.get_fastboot_output(["reboot"], allow_fail=True)
        if command_output and "rebooting" not in command_output.lower():
            raise JobError("Unable to fastboot reboot: %s" % command_output)
        else:
            lines = [
                status
                for status in command_output.split("\n")
                if "finished" in status.lower()
            ]
            if lines:
                self.results = {"status": lines[0].strip()}
            else:
                self.results = {"fail": self.name}
        return connection


class EnterFastbootAction(OptionalContainerFastbootAction, OptionalContainerAdbAction):
    """
    Enters fastboot bootloader.
    """

    name = "enter-fastboot-action"
    description = "enter fastboot bootloader"
    summary = "enter fastboot"
    command_exception = InfrastructureError

    def validate(self):
        super().validate()
        if "adb_serial_number" not in self.job.device:
            self.errors = "device adb serial number missing"
        elif self.job.device["adb_serial_number"] == "0000000000":
            self.errors = "device adb serial number unset"
        if "fastboot_serial_number" not in self.job.device:
            self.errors = "device fastboot serial number missing"
        elif self.job.device["fastboot_serial_number"] == "0000000000":
            self.errors = "device fastboot serial number unset"
        if "fastboot_options" not in self.job.device:
            self.errors = "device fastboot options missing"
        elif not isinstance(self.job.device["fastboot_options"], list):
            self.errors = "device fastboot options is not a list"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)

        # Try to enter fastboot mode with adb.
        adb_serial_number = self.job.device["adb_serial_number"]
        # start the adb daemon
        command_output = self.get_adb_output(["start-server"], allow_fail=True)
        if command_output and "successfully" in command_output:
            self.logger.debug("adb daemon started: %s", command_output)

        command_output = self.get_adb_output(["devices"], allow_fail=True)
        if command_output and adb_serial_number in command_output:
            self.logger.debug("Device is in adb: %s", command_output)
            self.run_adb(["reboot-bootloader"])
            return connection

        # Enter fastboot mode with fastboot.
        fastboot_serial_number = self.job.device["fastboot_serial_number"]
        command_output = self.get_fastboot_output(["devices"])

        if command_output and fastboot_serial_number in command_output:
            self.logger.debug("Device is in fastboot: %s", command_output)
            command_output = self.get_fastboot_output(["reboot-bootloader"])
            if command_output and "okay" not in command_output.lower():
                raise InfrastructureError(
                    "Unable to enter fastboot: %s" % command_output
                )
            else:
                lines = [
                    status
                    for status in command_output.split("\n")
                    if "finished" in status.lower()
                ]
                if lines:
                    self.results = {"status": lines[0].strip()}
                else:
                    self.results = {"fail": self.name}
        return connection
