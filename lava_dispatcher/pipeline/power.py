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


import yaml
from lava_dispatcher.pipeline.action import (
    Action,
    Pipeline,
    InfrastructureError,
    TestError,
)
from lava_dispatcher.pipeline.logical import AdjuvantAction
from lava_dispatcher.pipeline.utils.constants import SHUTDOWN_MESSAGE


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

    def run(self, connection, args=None):
        if not connection:
            raise RuntimeError("Called %s without an active Connection" % self.name)
        if self.job.device.power_state is 'off' and self.job.device.power_command is not '':  # power on action used instead
            return connection
        connection = super(RebootDevice, self).run(connection, args)
        connection.prompt_str = self.parameters.get('parameters', {}).get('shutdown-message', SHUTDOWN_MESSAGE)
        connection.sendline("reboot")
        # FIXME: possibly deployment data, possibly separate actions, possibly adjuvants.
        connection.sendline("reboot -n")  # initramfs may require -n for *now*
        connection.sendline("reboot -n -f")  # initrd may require -n for *now* and -f for *force*
        self.results = {'status': "success"}
        self.data[PDUReboot.key()] = False
        if 'bootloader_prompt' in self.data['common']:
            self.reboot_prompt = self.get_common_data('bootloader_prompt', 'prompt')
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

    def run(self, connection, args=None):
        connection = super(PDUReboot, self).run(connection, args)
        if not self.adjuvant:
            return connection
        if not self.job.device.hard_reset_command:
            raise InfrastructureError("Hard reset required but not defined for %s." % self.job.device['hostname'])
        command = self.job.device.hard_reset_command
        if not self.run_command(command.split(' ')):
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

    def run(self, connection, args=None):
        connection = super(PowerOn, self).run(connection, args)
        if self.job.device.power_state is 'off':
            command = self.job.device.power_command
            if not command:
                return connection
            if not self.run_command(command.split(' ')):
                raise InfrastructureError("%s command failed" % command)
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

    def run(self, connection, args=None):
        connection = super(PowerOff, self).run(connection, args)
        if not hasattr(self.job.device, 'power_state'):
            return connection
        if self.job.device.power_state is 'on':  # allow for '' and skip
            command = self.job.device['commands']['power_off']
            if not self.run_command(command.split(' ')):
                raise InfrastructureError("%s command failed" % command)
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

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(job=self.job, parent=self, parameters=parameters)
        self.internal_pipeline.add_action(PowerOff())

    def run(self, connection, args=None):
        """
        The pexpect.spawn here is the ShellCommand not the ShellSession connection object.
        So call the finalise() function of the connection which knows about the raw_connection inside.
        The internal_pipeline of FinalizeAction is special - it needs to run even in the case of error / cancel.
        """
        connection = super(FinalizeAction, self).run(connection, args)
        if connection:
            connection.finalise()
        for protocol in self.job.protocols:
            protocol.finalise_protocol()
        if self.errors:
            self.results = {'status': self.errors}
            self.logger.debug('status: %s' % self.errors)
        elif self.job.pipeline.errors:
            self.results = {'status': "Incomplete"}
            self.errors = "Incomplete"
            self.logger.error({
                'Status': 'Incomplete',
                'Errors': self.job.pipeline.errors})
        else:
            self.results = {'status': "Complete"}
            self.logger.debug("Status: Complete")
        with open("%s/results.yaml" % self.job.parameters['output_dir'], 'w') as results:
            results.write(yaml.dump(self.job.pipeline.describe()))
        # from meliae import scanner
        # scanner.dump_all_objects('filename.json')
