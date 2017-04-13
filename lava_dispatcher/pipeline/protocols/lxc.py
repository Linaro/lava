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


import re
import os
import yaml
import pexpect
import logging
import traceback
from lava_dispatcher.pipeline.connection import Protocol
from lava_dispatcher.pipeline.action import (
    InfrastructureError,
    LAVABug,
    TestError,
    JobError,
    Timeout,
)
from lava_dispatcher.pipeline.shell import ShellCommand
from lava_dispatcher.pipeline.utils.constants import (
    LAVA_LXC_TIMEOUT,
    LXC_PATH,
)
from lava_dispatcher.pipeline.utils.filesystem import lxc_path


class LxcProtocol(Protocol):  # pylint: disable=too-many-instance-attributes
    """
    Lxc API protocol.
    """
    name = "lava-lxc"

    def __init__(self, parameters, job_id):
        super(LxcProtocol, self).__init__(parameters, job_id)
        self.system_timeout = Timeout('system', LAVA_LXC_TIMEOUT)
        self.persistence = parameters['protocols'][self.name].get('persist',
                                                                  False)
        if self.persistence:
            self.lxc_name = parameters['protocols'][self.name]['name']
        else:
            self.lxc_name = '-'.join(
                [parameters['protocols'][self.name]['name'], str(job_id)])
        self.lxc_dist = parameters['protocols'][self.name]['distribution']
        self.lxc_release = parameters['protocols'][self.name]['release']
        self.lxc_arch = parameters['protocols'][self.name]['arch']
        self.lxc_template = parameters['protocols'][self.name].get(
            'template', 'download')
        self.lxc_mirror = parameters['protocols'][self.name].get('mirror',
                                                                 None)
        self.lxc_security_mirror = parameters['protocols'][self.name].get(
            'security_mirror', None)
        self.verbose = parameters['protocols'][self.name].get('verbose', False)
        self.fastboot_reboot = parameters.get('reboot_to_fastboot', True)
        self.custom_lxc_path = False
        if LXC_PATH != lxc_path(parameters['dispatcher']):
            self.custom_lxc_path = True
        self.logger = logging.getLogger('dispatcher')

    @classmethod
    def accepts(cls, parameters):  # pylint: disable=too-many-return-statements
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

    def _api_select(self, data, action=None):
        if not data:
            raise TestError("Protocol called without any data")
        if not action:
            raise LAVABug('LXC protocol needs to be called from an action.')
        if 'pre-os-command' in data:
            action.logger.info("Running pre OS command.")
            command = action.job.device.pre_os_command
            if not action.run_command(command.split(' '), allow_silent=True):
                raise InfrastructureError("%s failed" % command)

    def __call__(self, *args, **kwargs):
        action = None
        if kwargs is not None:
            if 'self' in kwargs:
                action = kwargs['self']
        logger = action.logger if action else logging.getLogger("dispatcher")
        try:
            return self._api_select(args, action=action)
        except yaml.YAMLError as exc:
            msg = re.sub(r'\s+', ' ', ''.join(traceback.format_exc().split('\n')))
            logger.exception(msg)
            raise JobError("Invalid call to %s %s" % (self.name, exc))

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
            self.logger.info("%s protocol: %s exists", self.name,
                             self.lxc_name)
            # Check if the container should persist
            if self.persistence:
                self.logger.debug("%s protocol: issue stop, to persist",
                                  self.name)
                cmd = "lxc-stop -n {0} -k".format(self.lxc_name)
                self.logger.debug("%s protocol: executing '%s'", self.name,
                                  cmd)
            else:
                self.logger.debug("%s protocol: destroy", self.name)
                if self.custom_lxc_path:
                    abs_path = os.path.realpath(os.path.join(LXC_PATH,
                                                             self.lxc_name))
                    cmd = "lxc-destroy -n {0} -f -P {1}".format(
                        self.lxc_name, os.path.dirname(abs_path))
                else:
                    cmd = "lxc-destroy -n {0} -f".format(self.lxc_name)
                self.logger.debug("%s protocol: executing '%s'", self.name,
                                  cmd)
            shell = ShellCommand("%s\n" % cmd, self.system_timeout,
                                 logger=self.logger)
            # execute the command.
            shell.expect(pexpect.EOF)
            if shell.exitstatus:
                raise InfrastructureError(
                    "%s command exited %d: %s" % (cmd, shell.exitstatus,
                                                  shell.readlines()))
            if self.custom_lxc_path and not self.persistence:
                os.remove(os.path.join(LXC_PATH, self.lxc_name))
        self.logger.debug("%s protocol finalised.", self.name)
