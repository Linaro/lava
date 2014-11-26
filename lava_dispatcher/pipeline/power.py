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
import logging
from lava_dispatcher.pipeline.action import (
    Action,
    Pipeline,
    AdjuvantAction,
    InfrastructureError,
    JobError,
    TestError,
)
from lava_dispatcher.pipeline.shell import ExpectShellSession


class ResetDevice(Action):
    """
    Used within a RetryAction - first tries 'reboot' then
    tries PDU
    """
    # FIXME: extend to know the power state of the device
    def __init__(self):
        super(ResetDevice, self).__init__()
        self.name = "reboot-device"
        self.description = "reboot or power-cycle the device"
        self.summary = "reboot the device"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        # self.internal_pipeline.add_action(ExpectShellSession())
        self.internal_pipeline.add_action(RebootDevice())
        self.internal_pipeline.add_action(PDUReboot())


class RebootDevice(Action):
    """
    Issues the reboot command on the board
    """
    def __init__(self):
        super(RebootDevice, self).__init__()
        self.name = "soft-reboot"
        self.summary = "reboot command sent to device"
        self.description = "attempt to reboot the running device"

    def run(self, connection, args=None):
        if not connection:
            raise RuntimeError("Called %s without an active Connection" % self.name)
        connection.prompt_str = 'The system is going down for reboot NOW'
        connection.sendline("reboot")
        self.results = {'status': "success"}
        try:
            connection.wait()
        except TestError:
            self.results = {'status': "failed"}
            self.data[PDUReboot.key()] = True
            connection.prompt_str = self.parameters['u-boot']['parameters']['bootloader_prompt']
        return connection


class PDUReboot(AdjuvantAction):
    """
    Issues the PDU power cycle command on the dispatcher
    Raises InfrastructureError if either the command fails
    (pdu client reports error) or if the connection times out
    waiting for the device to reset.
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

    def validate(self):
        super(PDUReboot, self).validate()
        if 'commands' not in self.job.device.parameters:
            return  # no PDU commands
        if 'hard_reset' not in self.job.device.parameters['commands']:
            return  # class will do nothing
        self.command = self.job.device.parameters['commands']['hard_reset']

    def run(self, connection, args=None):
        connection = super(PDUReboot, self).run(connection, args)
        if not self.adjuvant:
            self.logger.debug("Skipping adjuvant %s" % self.key())
            return connection
        if not self._run_command(self.command.split(' ')):
            raise InfrastructureError("%s failed" % self.command)
        try:
            connection.wait()
        except TestError:
            raise InfrastructureError("%s failed to reset device" % self.key())
        self.data[PDUReboot.key()] = False
        self.results = {'status': 'success'}
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
        if 'commands' in self.job.device.parameters and \
           'power_on' in self.job.device.parameters['commands']:
            command = self.job.device.parameters['commands']['power_on']
            if not self._run_command(command.split(' ')):
                raise InfrastructureError("%s command failed" % command)
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
        if 'commands' in self.job.device.parameters and \
           'power_off' in self.job.device.parameters['commands']:
            command = self.job.device.parameters['commands']['power_off']
            if not self._run_command(command.split(' ')):
                raise InfrastructureError("%s command failed" % command)
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
        self.summary = "finalize the job"
        self.description = "finish the process and cleanup"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(job=self.job, parent=self, parameters=parameters)
        self.internal_pipeline.add_action(PowerOff())

    def run(self, connection, args=None):
        """
        The pexpect.spawn here is the ShellCommand not the ShellSession connection object.
        So call the finalise() function of the connection which knows about the raw_connection inside.
        """
        connection = super(FinalizeAction, self).run(connection, args)
        if connection:
            connection.finalise()
        yaml_log = logging.getLogger("YAML")
        # FIXME: detect a Cancel and set status as Cancel
        if self.job.pipeline.errors:
            self.results = {'status': "Incomplete"}
            yaml_log.debug("Status: Incomplete")
            yaml_log.debug(self.job.pipeline.errors)
        else:
            self.results = {'status': "Complete"}
        with open("%s/results.yaml" % self.job.parameters['output_dir'], 'w') as results:
            results.write(yaml.dump(self.job.pipeline.describe()))
        # from meliae import scanner
        # scanner.dump_all_objects('filename.json')
