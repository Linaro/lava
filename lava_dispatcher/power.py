# Copyright (C) 2014-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# List just the subclasses supported for this base strategy
# imported by the parser to populate the list of subclasses.

import time
import traceback

from lava_common.constants import REBOOT_COMMAND_LIST
from lava_common.exceptions import InfrastructureError, JobError, TestError
from lava_common.timeout import Timeout
from lava_dispatcher.action import Action, Pipeline


class ResetDevice(Action):
    """
    Used within a RetryAction - If there is a hard reset, then tries that via
    PDUReboot, else tries issuing 'reboot' command either from device
    configuration (if configured) or from a constant list.
    """

    name = "reset-device"
    description = "reboot or power-cycle the device"
    summary = "reboot the device"

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if self.job.device.hard_reset_command:
            self.pipeline.add_action(PDUReboot())
        else:
            self.pipeline.add_action(SendRebootCommands())


class SendRebootCommands(Action):
    """
    Send reboot commands to the device
    """

    name = "send-reboot-commands"
    description = "Issue a reboot command on the device"
    summary = "Issue a reboot command on the device"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        if "soft_reboot" in self.parameters:
            commands = self.parameters["soft_reboot"]
        elif self.job.device.soft_reboot_command:
            commands = self.job.device.soft_reboot_command
        else:
            self.logger.warning(
                "No soft reboot command defined in the test job. Using defaults."
            )
            commands = REBOOT_COMMAND_LIST

        # Accept both str and [str]
        if isinstance(commands, str):
            commands = [commands]

        connection.prompt_str = self.parameters.get("parameters", {}).get(
            "shutdown-message", self.job.device.get_constant("shutdown-message")
        )
        connection.timeout = self.connection_timeout
        for cmd in commands:
            connection.sendline(cmd)
        try:
            self.wait(connection)
        except TestError:
            raise JobError("Soft reboot failed.")
        self.results = {"commands": commands}
        return connection


class PDUReboot(Action):
    """
    Issues the PDU power cycle command on the dispatcher
    Raises InfrastructureError if either the command fails
    (pdu client reports error) or if the connection times out
    waiting for the device to reset.
    It is an error for a device to fail to reboot after a
    soft reboot and a failed hard reset.
    """

    name = "pdu-reboot"
    description = "issue commands to a PDU to power cycle a device"
    summary = "hard reboot using PDU"
    timeout_exception = InfrastructureError
    command_exception = InfrastructureError

    def __init__(self):
        super().__init__()
        self.command = None

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        if not self.job.device.hard_reset_command:
            raise InfrastructureError("Hard reset required but not defined.")
        command = self.job.device.hard_reset_command
        if not isinstance(command, list):
            command = [command]
        for cmd in command:
            self.run_cmd(cmd, error_msg="Unable to reboot: '%s' failed" % cmd)
        self.results = {"status": "success"}
        return connection


class PrePower(Action):
    """
    Issue the configured pre-power command.

    Can be used to activate relays or other external hardware to change DUT
    operation before applying power. e.g. to set the OTG port to 'sync' so
    that the DUT is visible to fastboot.
    """

    name = "pre-power-command"
    description = "issue pre power command"
    summary = "send pre-power-command"
    timeout_exception = InfrastructureError
    command_exception = InfrastructureError

    def run(self, connection, max_end_time):
        if self.job.device.pre_power_command == "":
            self.logger.warning("Pre power command does not exist")
            return connection
        connection = super().run(connection, max_end_time)
        if self.job.device.pre_power_command:
            command = self.job.device.pre_power_command
            self.logger.info("Running pre power command")
            if not isinstance(command, list):
                command = [command]
            for cmd in command:
                self.run_cmd(
                    cmd, error_msg="Unable to run pre-power: '%s' failed" % cmd
                )
        self.results = {"success": self.name}
        return connection


class PreOs(Action):
    """
    Issue the configured pre-os command.

    Can be used to activate relays or other external hardware to change DUT
    operation before applying power. e.g. to set the OTG port to 'off' so that
    the DUT can use USB host.
    """

    name = "pre-os-command"
    description = "issue pre os command"
    summary = "send pre-os-command"
    timeout_exception = InfrastructureError
    command_exception = InfrastructureError

    def run(self, connection, max_end_time):
        if self.job.device.pre_os_command == "":
            self.logger.warning("Pre OS command does not exist")
            return connection
        connection = super().run(connection, max_end_time)
        if self.job.device.pre_os_command:
            command = self.job.device.pre_os_command
            self.logger.info("Running pre OS command")
            if not isinstance(command, list):
                command = [command]
            for cmd in command:
                self.run_cmd(cmd, error_msg="Unable to run pre-os: '%s' failed" % cmd)
        self.results = {"success": self.name}
        return connection


class PowerOn(Action):
    """
    Issues the power on command via the PDU
    """

    name = "power-on"
    description = "supply power to device"
    summary = "send power_on command"
    timeout_exception = InfrastructureError
    command_exception = InfrastructureError

    def run(self, connection, max_end_time):
        # to enable power to a device, either power_on or hard_reset are needed.
        if self.job.device.power_command == "":
            self.logger.warning("Unable to power on the device")
            return connection
        connection = super().run(connection, max_end_time)
        if self.job.device.pre_power_command:
            command = self.job.device.pre_power_command
            self.logger.info("Running pre power command")
            if not isinstance(command, list):
                command = [command]
            for cmd in command:
                self.run_cmd(cmd, error_msg="Unable to power-on: '%s' failed" % cmd)
        command = self.job.device.power_command
        if not command:
            return connection
        if not isinstance(command, list):
            command = [command]
        for cmd in command:
            self.run_cmd(cmd, error_msg="Unable to power-on: '%s' failed" % cmd)
        self.results = {"success": self.name}
        return connection


class PowerOff(Action):
    """
    Turns power off at the end of a job
    """

    name = "power-off"
    description = "discontinue power to device"
    summary = "send power_off command"
    timeout_exception = InfrastructureError
    command_exception = InfrastructureError

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        if not self.job.device.get("commands"):
            return connection
        command = self.job.device["commands"].get("power_off", [])
        # QEMU cannot use a power_off_command because that would be run
        # on the worker, not the VM.
        if not isinstance(command, list):
            command = [command]
        for cmd in command:
            self.run_cmd(cmd, error_msg="Unable to power-off: '%s' failed" % cmd)
        self.results = {"status": "success"}
        return connection


class ReadFeedback(Action):
    """
    Generalise the feedback support so that it can be added
    to any pipeline.
    """

    name = "read-feedback"
    description = "Check for messages on all other namespaces"
    summary = "Read from other namespaces"

    def __init__(self, finalize=False, repeat=False):
        super().__init__()
        self.finalize = finalize
        self.parameters["namespace"] = "common"
        self.duration = 1
        self.repeat = repeat

    def populate(self, parameters):
        super().populate(parameters)
        dur = (
            self.job.parameters.get("timeouts", {})
            .get("connections", {})
            .get("read-feedback")
        )
        if dur:
            self.duration = Timeout.parse(dur)

    def run(self, connection, max_end_time):
        feedbacks = []
        for feedback_ns in self.data.keys():
            if feedback_ns == self.parameters.get("namespace"):
                if not self.repeat:
                    continue
            feedback_connection = self.get_namespace_data(
                action="shared",
                label="shared",
                key="connection",
                deepcopy=False,
                parameters={"namespace": feedback_ns},
            )
            if feedback_connection:
                feedbacks.append((feedback_ns, feedback_connection))
            else:
                self.logger.debug("No connection for namespace %s", feedback_ns)
        for feedback in feedbacks:
            deadline = time.monotonic() + self.duration
            while True:
                timeout = max(deadline - time.monotonic(), 0)
                bytes_read = feedback[1].listen_feedback(
                    timeout=timeout, namespace=feedback[0]
                )
                # ignore empty or single newline-only content
                if bytes_read > 1:
                    self.logger.debug(
                        "Listened to connection for namespace '%s' for up to %ds",
                        feedback[0],
                        self.duration,
                    )
                # If we're not finalizing, we make only one attempt to read
                # feedback. Otherwise, we try to consume more output while
                # it's coming (i.e. until EOF or timeout expires).
                if not self.finalize or bytes_read == 0 or timeout == 0:
                    break
            if self.finalize:
                self.logger.info(
                    "Finalising connection for namespace '%s'", feedback[0]
                )
                # Finalize all connections associated with each namespace.
                feedback[1].finalise()
        super().run(connection, max_end_time)
        return connection


class FinalizeAction(Action):
    section = "finalize"
    name = "finalize"
    description = "finish the process and cleanup"
    summary = "finalize the job"

    def __init__(self):
        """
        The FinalizeAction is always added as the last Action in the top level pipeline by the parser.
        The tasks include finalising the connection (whatever is the last connection in the pipeline)
        and writing out the final pipeline structure containing the results as a logfile.
        """
        super().__init__()
        self.ran = False

    def populate(self, parameters):
        self.pipeline = Pipeline(job=self.job, parent=self, parameters=parameters)
        self.pipeline.add_action(PowerOff())
        self.pipeline.add_action(ReadFeedback(finalize=True, repeat=True))

    def run(self, connection, max_end_time):
        """
        The pexpect.spawn here is the ShellCommand not the ShellSession connection object.
        So call the finalise() function of the connection which knows about the raw_connection inside.
        The pipeline of FinalizeAction is special - it needs to run even in the case of error / cancel.
        """
        self.ran = True
        try:
            connection = super().run(connection, max_end_time)
            if connection:
                connection.finalise()
        except Exception as exc:
            self.logger.error("Failed to run '%s': %s", self.name, str(exc))
            self.logger.exception(traceback.format_exc())

        for protocol in self.job.protocols:
            protocol.finalise_protocol(self.job.device)
        return connection

    def cleanup(self, connection, max_end_time=None):
        # avoid running Finalize in validate or unit tests
        if not self.ran and self.job.started:
            if max_end_time is None:
                max_end_time = time.monotonic() + self.timeout.duration
            with self.timeout(self.job, max_end_time) as action_max_end_time:
                self.run(connection, action_max_end_time)
