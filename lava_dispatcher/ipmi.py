# Copyright (C) 2013 Linaro Limited
#
# Authors:
#   Antonio Terceiro <antonio.terceiro@linaro.org>
#   Michael Hudson-Doyle <michael.hudson@linaro.org>
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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import logging
import time
from lava_dispatcher.errors import CriticalError


class IPMITool(object):
    """
    This class wraps the ipmitool CLI to provide a convenient object-oriented
    API that can be composed into the implementation of devices that can be
    managed with IPMI.
    """

    def __init__(self, context, host, power_sleep, power_retries, ipmitool="ipmitool"):
        self.host = host
        self.context = context
        self.ipmitool = ipmitool
        self.power_sleep = power_sleep
        self.power_retries = power_retries

    def __ipmi(self, command):
        self.context.run_command(
            "%s -H %s -U admin -P admin %s" % (
                self.ipmitool, self.host, command
            ),
            failok=False
        )

    def __ipmi_cmd_output(self, command):
        return self.context.run_command_get_output(
            "%s -H %s -U admin -P admin %s" % (
                self.ipmitool, self.host, command)
        )

    def set_to_boot_from_disk(self):
        self.__ipmi("chassis bootdev disk")

    def set_to_boot_from_pxe(self):
        self.__ipmi("chassis bootdev pxe")

    def power_off(self):
        if self.get_power_status() == 'on':
            logging.debug("Powering off node")
            self.__ipmi("chassis power off")
        self.check_power_status('off')
        logging.debug("Node powered off")

    def power_on(self):
        if self.get_power_status() == 'off':
            logging.debug("Powering on node")
            self.__ipmi("chassis power on")
        self.check_power_status('on')
        logging.debug("Node powered on")

    def reset(self):
        self.__ipmi("chassis power reset")

    def check_power_status(self, check_status):
        power_status = None
        retries = 0
        while power_status != check_status and retries < self.power_retries:
            time.sleep(self.power_sleep)
            power_status = self.get_power_status()
            retries += 1
        if power_status != check_status:
            raise CriticalError("Failed to power node %s" % check_status)

    def get_power_status(self):
        """ Command 'ipmitool power status' will output 'Chassis Power is on'
            or 'Chassis Power is off'.
            Before we return the last string, the '\n' needs to be strip."""
        time.sleep(self.power_sleep)
        return self.__ipmi_cmd_output("power status").split(' ')[-1].rstrip()


class IpmiPxeBoot(object):
    """
    This class provides a convenient object-oriented API that can be
    used to initiate power on/off and boot device selection for pxe
    and disk boot devices using ipmi commands.
    """

    def __init__(self, context, host, power_sleep, power_retries):
        self.ipmitool = IPMITool(context, host, power_sleep, power_retries)

    def power_on_boot_master(self):
        self.ipmitool.power_off()
        self.ipmitool.power_on()

    def power_on_boot_image(self):
        self.ipmitool.set_to_boot_from_disk()
        self.ipmitool.power_off()
        self.ipmitool.power_on()

    def power_off(self):
        self.ipmitool.power_off()

    def power_on(self):
        self.ipmitool.power_on()
