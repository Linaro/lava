# Copyright (C) 2013 Linaro Limited
#
# Author: Dave Pigott <dave.pigott@linaro.org>
#         Fu Wei <fu.wei@linaro.org>
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

from lava_dispatcher.actions.lmp.board import lmp_send_command, lmp_set_identify, lmp_reset


def dut_disconnect(serial):
    lmp_send_command(serial, "sdmux", "dut", "disconnect", need_check_mode=True)


def dut_usda(serial):
    lmp_send_command(serial, "sdmux", "dut", "uSDA", need_check_mode=True)


def dut_usdb(serial):
    lmp_send_command(serial, "sdmux", "dut", "uSDB", need_check_mode=True)


def host_disconnect(serial):
    lmp_send_command(serial, "sdmux", "host", "disconnect", need_check_mode=True)


def host_usda(serial):
    lmp_send_command(serial, "sdmux", "host", "uSDA", need_check_mode=True)


def host_usdb(serial):
    lmp_send_command(serial, "sdmux", "host", "uSDB", need_check_mode=True)


def dut_power_off(serial):
    lmp_send_command(serial, "sdmux", "dut-power", "short-for-off", need_check_mode=True)


def dut_power_on(serial):
    lmp_send_command(serial, "sdmux", "dut-power", "short-for-on", need_check_mode=True)


def set_identify(serial, identify):
    if identify == "_on":
        lmp_set_identify(serial, "sdmux", True)
    elif identify == "off":
        lmp_set_identify(serial, "sdmux", False)


def reset(serial, reset_value=False):
    if reset_value is True:
        lmp_reset(serial, "sdmux", True)
    elif reset_value is False:
        lmp_reset(serial, "sdmux", False)
