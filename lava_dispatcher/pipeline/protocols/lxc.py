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
import logging
import traceback
import subprocess
from lava_dispatcher.pipeline.connection import Protocol
from lava_dispatcher.pipeline.action import (
    InfrastructureError,
    LAVABug,
    TestError,
    JobError,
    Timeout,
)
from lava_dispatcher.pipeline.utils.constants import (
    LAVA_LXC_TIMEOUT,
    LXC_PATH,
    UDEV_RULES_DIR,
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
        self.lxc_arch = parameters['protocols'][self.name].get('arch', None)
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
        return True

    def set_up(self):
        """
        Called from the job at the start of the run step.
        """
        pass

    def _api_select(self, data, action=None):
        if not data:
            raise TestError("[%s] Protocol called without any data." % self.name)
        if not action:
            raise LAVABug('LXC protocol needs to be called from an action.')
        for item in data:
            if 'request' not in item:
                raise LAVABug("[%s] Malformed protocol request data." % self.name)
            if 'pre-os-command' in item['request']:
                action.logger.info("[%s] Running pre OS command via protocol.", self.name)
                command = action.job.device.pre_os_command
                if not action.run_command(command.split(' '), allow_silent=True):
                    raise InfrastructureError("%s failed" % command)
                continue
            elif 'pre-power-command' in item['request']:
                action.logger.info("[%s] Running pre-power-command via protocol.", self.name)
                command = action.job.device.pre_power_command
                if not action.run_command(command.split(' '), allow_silent=True):
                    raise InfrastructureError("%s failed" % command)
                continue
            else:
                raise JobError("[%s] Unrecognised protocol request: %s" % (self.name, item))

    def __call__(self, *args, **kwargs):
        action = kwargs.get('action', None)
        logger = action.logger if action else logging.getLogger("dispatcher")
        self.logger.debug("[%s] Checking protocol data for %s", action.name, self.name)
        try:
            return self._api_select(args, action=action)
        except yaml.YAMLError as exc:
            msg = re.sub(r'\s+', ' ', ''.join(traceback.format_exc().split('\n')))
            logger.exception(msg)
            raise JobError("Invalid call to %s %s" % (self.name, exc))

    def _call_handler(self, command):
        try:
            self.logger.debug("%s protocol: executing '%s'", self.name, command)
            output = subprocess.check_output(command.split(' '),
                                             stderr=subprocess.STDOUT)
            if output:
                self.logger.debug(output)
        except subprocess.CalledProcessError:
            self.logger.debug("%s protocol: FAILED executing '%s'",
                              self.name, command)

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
                    self._call_handler(reboot_cmd)
        else:
            self.logger.info("%s protocol: device not rebooting to fastboot",
                             self.name)

        # Stop the container.
        self.logger.debug("%s protocol: issue stop", self.name)
        stop_cmd = "lxc-stop -n {0} -k".format(self.lxc_name)
        self._call_handler(stop_cmd)
        # Check if the container should persist and skip destroying it.
        if self.persistence:
            self.logger.debug("%s protocol: persistence requested",
                              self.name)
        else:
            self.logger.debug("%s protocol: issue destroy", self.name)
            if self.custom_lxc_path:
                abs_path = os.path.realpath(os.path.join(LXC_PATH,
                                                         self.lxc_name))
                destroy_cmd = "lxc-destroy -n {0} -f -P {1}".format(
                    self.lxc_name, os.path.dirname(abs_path))
            else:
                destroy_cmd = "lxc-destroy -n {0} -f".format(self.lxc_name)
            self._call_handler(destroy_cmd)
            if self.custom_lxc_path and not self.persistence:
                os.remove(os.path.join(LXC_PATH, self.lxc_name))
        # Remove udev rule which added device to the container and then reload
        # udev rules.
        rules_file = os.path.join(UDEV_RULES_DIR,
                                  '100-' + self.lxc_name + '.rules')
        if os.path.exists(rules_file):
            os.remove(rules_file)
            self.logger.debug("%s protocol: removed udev rules '%s'",
                              self.name, rules_file)
        reload_cmd = "udevadm control --reload-rules"
        self._call_handler(reload_cmd)
        self.logger.debug("%s protocol finalised.", self.name)
