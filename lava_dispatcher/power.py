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


from lava_dispatcher.action import (
    Action,
    InfrastructureError,
    Pipeline,
    JobError,
    TestError,
)
from lava_dispatcher.utils.constants import REBOOT_COMMAND_LIST

# pylint: disable=missing-docstring


class ResetDevice(Action):
    """
    Used within a RetryAction - first tries 'reboot' then
    tries PDU.
    """
    def __init__(self):
        super(ResetDevice, self).__init__()
        self.name = "reset-device"
        self.description = "reboot or power-cycle the device"
        self.summary = "reboot the device"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        if self.job.device.hard_reset_command:
            self.internal_pipeline.add_action(PDUReboot())
        else:
            self.internal_pipeline.add_action(SendRebootCommands())


class SendRebootCommands(Action):
    """
    Send reboot commands to the device
    """

    def __init__(self):
        super(SendRebootCommands, self).__init__()
        self.name = "send-reboot-commands"
        self.summary = 'Issue a reboot command on the device'
        self.description = 'Issue a reboot command on the device'

    def run(self, connection, max_end_time, args=None):
        connection = super(SendRebootCommands, self).run(connection, max_end_time, args)
        reboot_commands = self.parameters.get('soft_reboot', [])  # list
        if not self.parameters.get('soft_reboot', None):  # unit test
            self.logger.warning('No soft reboot command defined in the test job. Using defaults.')
            reboot_commands = REBOOT_COMMAND_LIST
        connection.prompt_str = self.parameters.get(
            'parameters', {}).get('shutdown-message', self.job.device.get_constant('shutdown-message'))
        connection.timeout = self.connection_timeout
        for cmd in reboot_commands:
            connection.sendline(cmd)
        try:
            self.wait(connection)
        except TestError:
            raise JobError("Soft reboot failed.")
        self.results = {'commands': reboot_commands}
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
    def __init__(self):
        super(PDUReboot, self).__init__()
        self.name = "pdu-reboot"
        self.summary = "hard reboot using PDU"
        self.description = "issue commands to a PDU to power cycle a device"
        self.command = None

    def run(self, connection, max_end_time, args=None):
        connection = super(PDUReboot, self).run(connection, max_end_time, args)
        if not self.job.device.hard_reset_command:
            raise InfrastructureError("Hard reset required but not defined.")
        command = self.job.device.hard_reset_command
        if not isinstance(command, list):
            command = [command]
        for cmd in command:
            if not self.run_command(cmd.split(' '), allow_silent=True):
                raise InfrastructureError("%s failed" % cmd)
        self.results = {'status': 'success'}
        return connection


class PowerOn(Action):
    """
    Issues the power on command via the PDU
    """
    def __init__(self):
        super(PowerOn, self).__init__()
        self.name = "power-on"
        self.summary = "send power_on command"
        self.description = "supply power to device"

    def run(self, connection, max_end_time, args=None):
        # to enable power to a device, either power_on or hard_reset are needed.
        if self.job.device.power_command is '':
            self.logger.warning("Unable to power on the device")
            return connection
        connection = super(PowerOn, self).run(connection, max_end_time, args)
        if self.job.device.pre_power_command:
            command = self.job.device.pre_power_command
            self.logger.info("Running pre power command")
            if not isinstance(command, list):
                command = [command]
            for cmd in command:
                if not self.run_command(cmd.split(' '), allow_silent=True):
                    raise InfrastructureError("%s failed" % cmd)
        command = self.job.device.power_command
        if not command:
            return connection
        if not isinstance(command, list):
            command = [command]
        for cmd in command:
            if not self.run_command(cmd.split(' '), allow_silent=True):  # pylint: disable=no-member
                raise InfrastructureError("%s failed" % cmd)
        self.results = {'success': self.name}
        return connection


class PowerOff(Action):
    """
    Turns power off at the end of a job
    """
    def __init__(self):
        super(PowerOff, self).__init__()
        self.name = "power-off"
        self.summary = "send power_off command"
        self.description = "discontinue power to device"

    def run(self, connection, max_end_time, args=None):
        connection = super(PowerOff, self).run(connection, max_end_time, args)
        if not self.job.device.get('commands', None):
            return connection
        command = self.job.device['commands'].get('power_off', [])
        if not isinstance(command, list):
            command = [command]
        for cmd in command:
            if not self.run_command(cmd.split(' '), allow_silent=True):
                raise InfrastructureError("%s failed" % cmd)
        self.results = {'status': 'success'}
        return connection


class ReadFeedback(Action):
    """
    Generalise the feedback support so that it can be added
    to any pipeline.
    """
    def __init__(self, finalize=False, repeat=False):
        super(ReadFeedback, self).__init__()
        self.name = 'read-feedback'
        self.summary = 'Read from other namespaces'
        self.description = 'Check for messages on all other namespaces'
        self.finalize = finalize
        self.parameters['namespace'] = 'common'
        self.duration = 1  # FIXME: needs to be a constant set in the base template.
        self.repeat = repeat

    def run(self, connection, max_end_time, args=None):
        feedbacks = []
        for feedback_ns in self.data.keys():  # pylint: disable=no-member
            if feedback_ns == self.parameters.get('namespace'):
                if not self.repeat:
                    continue
            feedback_connection = self.get_namespace_data(
                action='shared', label='shared', key='connection',
                deepcopy=False, parameters={"namespace": feedback_ns})
            if feedback_connection:
                feedbacks.append((feedback_ns, feedback_connection))
        for feedback in feedbacks:
            bytes_read = feedback[1].listen_feedback(timeout=self.duration)
            # ignore empty or single newline-only content
            if bytes_read > 1:
                self.logger.debug(
                    "Listened to connection for namespace '%s' for %ds", feedback[0], self.duration)
            if self.finalize:
                # Finalize all connections associated with each namespace.
                feedback[1].finalise()
        return connection


class FinalizeAction(Action):

    def __init__(self):
        """
        The FinalizeAction is always added as the last Action in the top level pipeline by the parser.
        The tasks include finalising the connection (whatever is the last connection in the pipeline)
        and writing out the final pipeline structure containing the results as a logfile.
        """
        super(FinalizeAction, self).__init__()
        self.name = "finalize"
        self.section = 'finalize'
        self.summary = "finalize the job"
        self.description = "finish the process and cleanup"
        self.ran = False

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(job=self.job, parent=self, parameters=parameters)
        self.internal_pipeline.add_action(PowerOff())
        self.internal_pipeline.add_action(ReadFeedback(finalize=True))

    def run(self, connection, max_end_time, args=None):
        """
        The pexpect.spawn here is the ShellCommand not the ShellSession connection object.
        So call the finalise() function of the connection which knows about the raw_connection inside.
        The internal_pipeline of FinalizeAction is special - it needs to run even in the case of error / cancel.
        """
        self.ran = True
        try:
            connection = super(FinalizeAction, self).run(connection, max_end_time, args)
            if connection:
                connection.finalise()

        except Exception as exc:  # pylint: disable=unused-variable,broad-except
            pass
        finally:
            for protocol in self.job.protocols:
                protocol.finalise_protocol(self.job.device)
        return connection

    def cleanup(self, connection):
        # avoid running Finalize in validate or unit tests
        if not self.ran and self.job.started:
            self.run(connection, None, None)
