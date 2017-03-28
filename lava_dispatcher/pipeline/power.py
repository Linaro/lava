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
    TestError,
)
from lava_dispatcher.pipeline.logical import AdjuvantAction


class ResetDevice(Action):
    """
    Used within a RetryAction - first tries 'reboot' then
    tries PDU. If the device supports power_state, the
    internal pipeline actions will use the value to skip
    waiting for certain prompts.
    """
    def __init__(self):
        super(ResetDevice, self).__init__()
        self.name = "reboot-device"
        self.description = "reboot or power-cycle the device"
        self.summary = "reboot the device"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        self.internal_pipeline.add_action(RebootDevice())  # skipped if power is off
        self.internal_pipeline.add_action(PDUReboot())  # adjuvant, only if RebootDevice acts and fails
        self.internal_pipeline.add_action(PowerOn())


class RebootDevice(Action):
    """
    Issues the reboot command on the board
    """
    def __init__(self):
        super(RebootDevice, self).__init__()
        self.name = "soft-reboot"
        self.summary = "reboot command sent to device"
        self.description = "attempt to reboot the running device"
        self.reboot_prompt = None

    def run(self, connection, max_end_time, args=None):
        if not connection:
            raise LAVABug("Called %s without an active Connection" % self.name)
        if self.job.device.power_state is 'off' and self.job.device.power_command is not '':  # power on action used instead
            return connection
        if self.job.device.power_state is 'on' and self.job.device.soft_reset_command is not '':
            command = self.job.device['commands']['soft_reset']
            if isinstance(command, list):
                for cmd in command:
                    if not self.run_command(cmd.split(' '), allow_silent=True):
                        raise InfrastructureError("%s failed" % cmd)
            else:
                if not self.run_command(command.split(' '), allow_silent=True):
                    raise InfrastructureError("%s failed" % command)
            self.results = {"success": self.job.device.power_state}
        else:
            connection = super(RebootDevice, self).run(connection, max_end_time, args)
            connection.prompt_str = self.parameters.get('parameters', {}).get('shutdown-message', self.job.device.get_constant('shutdown-message'))
            connection.timeout = self.connection_timeout
            connection.sendline("reboot")
            # FIXME: possibly deployment data, possibly separate actions, possibly adjuvants.
            connection.sendline("reboot -n")  # initramfs may require -n for *now*
            connection.sendline("reboot -n -f")  # initrd may require -n for *now* and -f for *force*
        self.results = {"success": connection.prompt_str}
        self.data[PDUReboot.key()] = False
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
            self.logger.info("Wait for prompt after soft reboot failed")
            self.results = {'status': "failed"}
            self.data[PDUReboot.key()] = True
            connection.prompt_str = self.reboot_prompt
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
        return 'pdu_reboot'

    def run(self, connection, max_end_time, args=None):
        connection = super(PDUReboot, self).run(connection, max_end_time, args)
        if not self.adjuvant:
            return connection
        if not self.job.device.hard_reset_command:
            raise InfrastructureError("Hard reset required but not defined for %s." % self.job.device['hostname'])
        command = self.job.device.hard_reset_command
        if isinstance(command, list):
            for cmd in command:
                if not self.run_command(cmd.split(' '), allow_silent=True):
                    raise InfrastructureError("%s failed" % cmd)
        else:
            if not self.run_command(command.split(' '), allow_silent=True):
                raise InfrastructureError("%s failed" % command)
        try:
            self.wait(connection)
        except TestError:
            raise InfrastructureError("%s failed to reset device" % self.key())
        self.data[PDUReboot.key()] = False
        self.results = {'status': 'success'}
        self.job.device.power_state = 'on'
        return connection


class PowerOn(Action):
    """
    Issues the power on command via the PDU
    """
    def __init__(self):
        super(PowerOn, self).__init__()
        self.name = "power_on"
        self.summary = "send power_on command"
        self.description = "supply power to device"

    def run(self, connection, max_end_time, args=None):
        connection = super(PowerOn, self).run(connection, max_end_time, args)
        if self.job.device.power_state is 'off':
            if self.job.device.pre_power_command:
                command = self.job.device.pre_power_command
                self.logger.info("Running pre power command")
                if isinstance(command, list):
                    for cmd in command:
                        if not self.run_command(cmd.split(' '), allow_silent=True):
                            raise InfrastructureError("%s failed" % cmd)
                else:
                    if not self.run_command(command.split(' '), allow_silent=True):
                        raise InfrastructureError("%s failed" % command)
            command = self.job.device.power_command
            if not command:
                return connection
            if isinstance(command, list):
                for cmd in command:
                    if not self.run_command(cmd.split(' '), allow_silent=True):
                        raise InfrastructureError("%s failed" % cmd)
            else:
                if not self.run_command(command.split(' '), allow_silent=True):
                    raise InfrastructureError("%s failed" % command)
            self.results = {'success': self.name}
            self.job.device.power_state = 'on'
        return connection


class PowerOff(Action):
    """
    Turns power off at the end of a job
    """
    def __init__(self):
        super(PowerOff, self).__init__()
        self.name = "power_off"
        self.summary = "send power_off command"
        self.description = "discontinue power to device"

    def run(self, connection, max_end_time, args=None):
        connection = super(PowerOff, self).run(connection, max_end_time, args)
        if not hasattr(self.job.device, 'power_state'):
            return connection
        if self.job.device.power_state is 'on':  # allow for '' and skip
            command = self.job.device['commands']['power_off']
            if isinstance(command, list):
                for cmd in command:
                    if not self.run_command(cmd.split(' '), allow_silent=True):
                        raise InfrastructureError("%s failed" % cmd)
            else:
                if not self.run_command(command.split(' '), allow_silent=True):
                    raise InfrastructureError("%s failed" % command)
            self.results = {'status': 'success'}
            self.job.device.power_state = 'off'
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
        if not self.ran:
            self.run(connection, None, None)
