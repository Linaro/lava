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


def disconnect(serial):
    lmp_send_command(serial, "hdmi", "hdmi", "disconnect")


def passthru(serial):
    lmp_send_command(serial, "hdmi", "hdmi", "passthru")


def fake(serial):
    lmp_send_command(serial, "hdmi", "hdmi", "fake")


def set_identify(serial, identify):
    if identify == "_on":
        lmp_set_identify(serial, "hdmi", True)
    elif identify == "off":
        lmp_set_identify(serial, "hdmi", False)


def reset(serial, reset_value=False):
    if reset_value is True:
        lmp_reset(serial, "hdmi", True)
    elif reset_value is False:
        lmp_reset(serial, "hdmi", False)
