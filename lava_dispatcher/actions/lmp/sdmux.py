# Copyright (C) 2013 Linaro Limited
#
# Author: Dave Pigott <dave.pigott@linaro.org>
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

from lava_dispatcher.actions.lmp.board import lmp_send_command


def dut_disconnect(serial):
    lmp_send_command(serial, "sdmux", "dut", "disconnect")


def dut_usda(serial):
    lmp_send_command(serial, "sdmux", "dut", "uSDA")


def dut_usdb(serial):
    lmp_send_command(serial, "sdmux", "dut", "uSDB")


def host_disconnect(serial):
    lmp_send_command(serial, "sdmux", "host", "disconnect")


def host_usda(serial):
    lmp_send_command(serial, "sdmux", "host", "uSDA")


def host_usdb(serial):
    lmp_send_command(serial, "sdmux", "host", "uSDB")


def dut_power_off(serial):
    lmp_send_command(serial, "sdmux", "dut-power", "short-for-off")


def dut_power_on(serial):
    lmp_send_command(serial, "sdmux", "dut-power", "short-for-on")
