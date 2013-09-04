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

from lava_dispatcher.actions.lmp.master import lmp_send_command


def audio_disconnect(serial):
    lmp_send_command(serial, "lsgpio", "audio", "disconnect")


def audio_passthru(serial):
    lmp_send_command(serial, "lsgpio", "audio", "passthru")


def a_dir_in(serial):
    lmp_send_command(serial, "lsgpio", "a-dir", "in")


def a_dir_out(serial):
    lmp_send_command(serial, "lsgpio", "a-dir", "out")


def b_dir_in(serial):
    lmp_send_command(serial, "lsgpio", "b-dir", "in")


def b_dir_out(serial):
    lmp_send_command(serial, "lsgpio", "b-dir", "out")
