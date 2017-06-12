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


from lava_dispatcher.pipeline.action import (
    Action,
    InfrastructureError,
    LAVABug,
    Pipeline,
    JobError,
    TestError,
)
from lava_dispatcher.pipeline.logical import AdjuvantAction
from lava_dispatcher.pipeline.utils.constants import REBOOT_COMMAND_LIST


class ResetDevice(Action):
    """
    Used within a RetryAction - first tries 'reboot' then
    tries PDU.
    """
    def __init__(self):
        super(ResetDevice, self).__init__()
        self.name = "reboot-device"
        self.description = "reboot or power-cycle the device"
        self.summary = "reboot the device"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(RebootDevice())  # uses soft_reset_command, if set
        self.internal_pipeline.add_action(PDUReboot())  # adjuvant, only if RebootDevice acts and fails
        self.internal_pipeline.add_action(SoftReboot())  # adjuvant, replaces PDUReboot if no power commands
        self.internal_pipeline.add_action(PowerOn())


class RebootDevice(Action):
    """
    Issues the reboot command on the board
    """
    def __init__(self):
        super(RebootDevice, self).__init__()
        self.name = "soft-reboot"
        self.summary = "configured reboot command sent to device"
        self.description = "attempt to reboot the running device using device-specific command."
        self.reboot_prompt = None

    def run(self, connection, max_end_time, args=None):
        if not connection:
            raise LAVABug("Called %s without an active Connection" % self.name)
        connection = super(RebootDevice, self).run(connection, max_end_time, args)
        self.set_namespace_data(action=PDUReboot.key(), label=PDUReboot.key(), key=PDUReboot.key(), value=True)
        self.set_namespace_data(action=SoftReboot.key(), label=SoftReboot.key(), key=SoftReboot.key(), value=True)
        if self.job.device.soft_reset_command is '':
            return connection
        command = self.job.device['commands']['soft_reset']
        if not isinstance(command, list):
            command = [command]
        for cmd in command:
            if not self.run_command(cmd.split(' '), allow_silent=True):
                raise InfrastructureError("%s failed" % cmd)
        self.results = {"success": connection.prompt_str}
        self.set_namespace_data(action=PDUReboot.key(), label=PDUReboot.key(), key=PDUReboot.key(), value=False)
        self.set_namespace_data(action=SoftReboot.key(), label=SoftReboot.key(), key=SoftReboot.key(), value=False)
        # FIXME: this should not be just based on UBoot, use shared action
        reboot_prompt = self.get_namespace_data(
            action='uboot-retry',
            label='bootloader_prompt',
            key='prompt'
        )
        if reboot_prompt:
            self.reboot_prompt = reboot_prompt
        try:
            self.wait(connection)
        except TestError:
            self.logger.info("Wait for prompt after soft reboot command failed")
            self.results = {'status': "failed"}
            self.set_namespace_data(action=PDUReboot.key(), label=PDUReboot.key(), key=PDUReboot.key(), value=True)
            connection.prompt_str = self.reboot_prompt
        return connection


class SoftReboot(AdjuvantAction):
    """
    If no remote power commands are available, trigger an attempt
    at a soft reboot using job level commands.
    """

    def __init__(self):
        self.name = SoftReboot.key()
        super(SoftReboot, self).__init__()
        self.summary = 'Issue a reboot command'
        self.description = 'Attempt a pre-defined soft reboot command.'

    @classmethod
    def key(cls):
        return 'send-reboot-command'

    def run(self, connection, max_end_time, args=None):
        connection = super(SoftReboot, self).run(connection, max_end_time, args)
        reboot_commands = self.parameters.get('soft_reboot', [])  # list
        if not self.adjuvant:
            return connection
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
        self.set_namespace_data(action=SoftReboot.key(), label=SoftReboot.key(), key=SoftReboot.key(), value=False)
        self.results = {'commands': reboot_commands}
        return connection


class PDUReboot(AdjuvantAction):
    """
    Issues the PDU power cycle command on the dispatcher
    Raises InfrastructureError if either the command fails
    (pdu client reports error) or if the connection times out
    waiting for the device to reset.
    It is an error for a device to fail to reboot after a
    soft reboot and a failed hard reset.
    """
    def __init__(self):
        self.name = PDUReboot.key()
        super(PDUReboot, self).__init__()
        self.summary = "hard reboot"
        self.description = "issue commands to a PDU to power cycle a device"
        self.command = None

    @classmethod
    def key(cls):
        return 'pdu-reboot'

    def run(self, connection, max_end_time, args=None):
        connection = super(PDUReboot, self).run(connection, max_end_time, args)
        if not self.adjuvant:
            return connection
        if not self.job.device.hard_reset_command:
            self.logger.warning("Hard reset required but not defined.")
            return connection
        command = self.job.device.hard_reset_command
        if not isinstance(command, list):
            command = [command]
        for cmd in command:
            if not self.run_command(cmd.split(' '), allow_silent=True):
                raise InfrastructureError("%s failed" % cmd)
        # the next prompt has to be determined by the boot method, so don't wait here.
        self.set_namespace_data(action=SoftReboot.key(), label=SoftReboot.key(), key=SoftReboot.key(), value=False)
        self.set_namespace_data(action=PDUReboot.key(), label=PDUReboot.key(), key=PDUReboot.key(), value=False)
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

    def run(self, connection, max_end_time, args=None):
        """
        The pexpect.spawn here is the ShellCommand not the ShellSession connection object.
        So call the finalise() function of the connection which knows about the raw_connection inside.
        The internal_pipeline of FinalizeAction is special - it needs to run even in the case of error / cancel.
        """
        self.ran = True
        connection = super(FinalizeAction, self).run(connection, max_end_time, args)
        if connection:
            connection.finalise()

        # Finalize all connections associated with each namespace.
        connection = self.get_namespace_data(action='shared', label='shared', key='connection', deepcopy=False)
        if connection:
            connection.finalise()

        for protocol in self.job.protocols:
            protocol.finalise_protocol(self.job.device)

    def cleanup(self, connection):
        # avoid running Finalize in validate or unit tests
        if not self.ran and self.job.started:
            self.run(connection, None, None)
