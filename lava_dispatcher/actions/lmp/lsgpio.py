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

import logging
from lava_dispatcher.actions.lmp.board import (
    lmp_send_command,
    lmp_send_multi_command,
    get_one_of_report,
    lmp_set_identify,
    lmp_reset
)


def _get_port_value(bus_array, port):
    if port == "a":
        return bus_array[0]["data"]
    elif port == "b":
        return bus_array[1]["data"]
    else:
        return None


def _get_port_type(bus_array, port):
    if port == "a":
        return bus_array[0]["type"]
    elif port == "b":
        return bus_array[1]["type"]
    else:
        return None


def _validate_gpio_data(data):
    xdigit = "0123456789abcdef"
    if len(data) == 2 and data.lower()[0] in xdigit and data.lower()[1] in xdigit:
        return True
    else:
        return False


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


def a_data_out(serial, data):
    if _validate_gpio_data(data) is True:
        mode_selection_dict = {'a-dir': 'out', 'a-data': data}
        lmp_send_multi_command(serial, "lsgpio", mode_selection_dict)
    else:
        logging.error("LMP LSGPIO: Error output date format for port a!")


def b_data_out(serial, data):
    if _validate_gpio_data(data) is True:
        mode_selection_dict = {'b-dir': 'out', 'b-data': data}
        lmp_send_multi_command(serial, "lsgpio", mode_selection_dict)
    else:
        logging.error("LMP LSGPIO: Error output date format for port b!")


def a_data_in(serial):
    response = lmp_send_command(serial, "lsgpio", "a-dir", "in")
    report_lsgpio = get_one_of_report(response, "lsgpio")
    return _get_port_value(report_lsgpio["bus"], "a")


def b_data_in(serial):
    response = lmp_send_command(serial, "lsgpio", "b-dir", "in")
    report_lsgpio = get_one_of_report(response, "lsgpio")
    return _get_port_value(report_lsgpio["bus"], "b")


def set_identify(serial, identify):
    if identify == "_on":
        lmp_set_identify(serial, "lsgpio", True)
    elif identify == "off":
        lmp_set_identify(serial, "lsgpio", False)


def reset(serial, reset_value=False):
    if reset_value is True:
        lmp_reset(serial, "lsgpio", True)
    elif reset_value is False:
        lmp_reset(serial, "lsgpio", False)
