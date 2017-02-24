# Copyright (C) 2015 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
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


import pexpect
import logging
from lava_dispatcher.pipeline.connection import Protocol
from lava_dispatcher.pipeline.action import (
    InfrastructureError,
    Timeout,
)
from lava_dispatcher.pipeline.shell import ShellCommand
from lava_dispatcher.pipeline.utils.constants import LAVA_LXC_TIMEOUT


class LxcProtocol(Protocol):
    """
    Lxc API protocol.
    """
    name = "lava-lxc"

    def __init__(self, parameters, job_id):
        super(LxcProtocol, self).__init__(parameters, job_id)
        self.system_timeout = Timeout('system', LAVA_LXC_TIMEOUT)
        self.lxc_name = '-'.join([parameters['protocols'][self.name]['name'],
                                  str(job_id)])
        self.lxc_dist = parameters['protocols'][self.name]['distribution']
        self.lxc_release = parameters['protocols'][self.name]['release']
        self.lxc_arch = parameters['protocols'][self.name]['arch']
        self.lxc_template = parameters['protocols'][self.name].get(
            'template', 'download')
        self.lxc_mirror = parameters['protocols'][self.name].get('mirror',
                                                                 None)
        self.lxc_security_mirror = parameters['protocols'][self.name].get(
            'security_mirror', None)
        self.fastboot_reboot = parameters.get('reboot_to_fastboot', True)
        self.logger = logging.getLogger('dispatcher')

    @classmethod
    def accepts(cls, parameters):
        if 'protocols' not in parameters:
            return False
        if 'lava-lxc' not in parameters['protocols']:
            return False
        if 'name' not in parameters['protocols']['lava-lxc']:
            return False
        if 'distribution' not in parameters['protocols']['lava-lxc']:
            return False
        if 'release' not in parameters['protocols']['lava-lxc']:
            return False
        if 'arch' not in parameters['protocols']['lava-lxc']:
            return False
        return True

    def set_up(self):
        """
        Called from the job at the start of the run step.
        """
        pass

    def finalise_protocol(self, device=None):
        """Called by Finalize action to power down and clean up the assigned
        device.
        """
        # Reboot devices to bootloader if required, based on the availability
        # of power cycle option and adb_serial_number.
        # Do not reboot to bootloader if 'reboot_to_fastboot' is set to
        # 'false' in job definition.
        if self.fastboot_reboot:
            if 'adb_serial_number' in device and hasattr(device, 'power_state'):
                if device.power_state not in ['on', 'off']:
                    reboot_cmd = "lxc-attach -n {0} -- adb reboot bootloader".format(self.lxc_name)
                    self.logger.debug("%s protocol: executing '%s'", self.name,
                                      reboot_cmd)
                    shell = ShellCommand("%s\n" % reboot_cmd,
                                         self.system_timeout,
                                         logger=self.logger)
                    # execute the command.
                    shell.expect(pexpect.EOF)
                    if shell.exitstatus:
                        self.logger.debug("%s command exited %d: %s",
                                          reboot_cmd,
                                          shell.exitstatus, shell.readlines())
        else:
            self.logger.info("%s protocol: device not rebooting to fastboot",
                             self.name)

        # ShellCommand executes the destroy command after checking for the
        # existance of the container
        cmd = "lxc-info -p -n {0}".format(self.lxc_name)
        self.logger.debug("%s protocol: executing '%s'", self.name, cmd)
        shell = ShellCommand("%s\n" % cmd, self.system_timeout,
                             logger=self.logger)
        # execute the command.
        shell.expect(pexpect.EOF)
        if not shell.exitstatus:
            self.logger.info("%s protocol: %s exists, proceed to destroy",
                             self.name, self.lxc_name)
            cmd = "lxc-destroy -n {0} -f".format(self.lxc_name)
            self.logger.debug("%s protocol: executing '%s'", self.name, cmd)
            shell = ShellCommand("%s\n" % cmd, self.system_timeout,
                                 logger=self.logger)
            # execute the command.
            shell.expect(pexpect.EOF)
            if shell.exitstatus:
                raise InfrastructureError("%s command exited %d: %s" % (cmd,
                                                                        shell.exitstatus,
                                                                        shell.readlines()))
        self.logger.debug("%s protocol finalised.", self.name)
