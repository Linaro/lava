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


class IPMITool(object):
    """
    This class wraps the ipmitool CLI to provide a convenient object-oriented
    API that can be composed into the implementation of devices that can be
    managed with IPMI.
    """

    def __init__(self, context, host, ipmitool="ipmitool"):
        self.host = host
        self.context = context
        self.ipmitool = ipmitool

    def __ipmi(self, command):
        self.context.run_command(
            "%s -H %s -U admin -P admin %s" % (
                self.ipmitool, self.host, command
            ),
            failok=False
        )

    def set_to_boot_from_disk(self):
        self.__ipmi("chassis bootdev disk")

    def set_to_boot_from_pxe(self):
        self.__ipmi("chassis bootdev pxe")

    def power_off(self):
        self.__ipmi("chassis power off")

    def power_on(self):
        self.__ipmi("chassis power on")

    def reset(self):
        self.__ipmi("chassis power reset")


class IpmiPxeBoot(object):
    """
    This class provides a convenient object-oriented API that can be
    used to initiate power on/off and boot device selection for pxe
    and disk boot devices using ipmi commands.
    """

    def __init__(self, context, host):
        self.ipmitool = IPMITool(context, host)

    def power_on_boot_master(self):
        self.ipmitool.set_to_boot_from_pxe()
        self.ipmitool.power_off()
        self.ipmitool.power_on()

    def power_on_boot_image(self):
        self.ipmitool.set_to_boot_from_disk()
        self.ipmitool.power_off()
        self.ipmitool.power_on()

    def power_off(self):
        self.ipmitool.power_off()
