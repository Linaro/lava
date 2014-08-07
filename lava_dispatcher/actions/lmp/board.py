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

import serial
import time
import json
import logging
from serial import (
    serialutil
)
from lava_dispatcher.errors import (
    CriticalError,
)


class LAVALmpDeviceSerial(object):
    def __init__(self, serialno, board_type, need_check_mode):
        device_map = {
            "sdmux": "0a",
            "sata": "19",
            "eth": "16",
            "lsgpio": "09",
            "hdmi": "0c",
            "usb": "04"
        }

        # Those devices don't broadcast their status contiguously,
        # they need a trigger signal.
        quiet_device = ["eth", "sata", "lsgpio"]

        self.timeout = 10
        self.retry = 3
        self.start_of_frame = '\x02'
        self.end_of_frame = '\x04'

        self.lmp_type_stream = "org.linaro.lmp." + board_type
        self.board_type = board_type
        if board_type in quiet_device:
            self.need_info_trigger = True
        else:
            self.need_info_trigger = False

        # With some boards, we must wait until the device has switched to the requested state.
        # Not all Lmp modules provide the required state information in the same format, for now.
        # So we make this function as an option, the default value is True.
        # TODO: Fix firmware so that they all do
        self.need_check_mode = need_check_mode

        # Generate the full serial number for the module.
        # "LL" + 2 board type code [xx] + 12 serial number [xxxxxxxxxxxx]
        # ('x' is hexadecimal code)
        self.serialno = "LL" + device_map[board_type] + serialno.zfill(12)
        logging.debug("LMP Serial #: %s" % self.serialno)

        # Connect to the module by Pyserial
        try:
            self.port = serial.Serial("/dev/serial/by-id/usb-Linaro_Ltd_LavaLMP_" + self.serialno + "-if00", timeout=1)
        except serial.serialutil.SerialException as e:
            logging.error("LMP: Error opening {0:s}: {1:s}".format(self.serialno, e))
            raise

        # It is a mandatory step to start operate a LMP module
        self.send_frame('{"schema":"org.linaro.lmp.info"}')

        # Get "board" info from the module, and check the serial number.
        self.info = self.get_response("board")
        if self.info['serial'] != self.serialno:
            raise CriticalError("LMP %s not connected" % serial)
        else:
            logging.debug("LMP %s is connected" % self.serialno)

    def send_frame(self, command):
        """ A simple function for sending raw message to module
        """
        logging.debug("LMP: Sending %s" % command)
        payload = self.start_of_frame + command + self.end_of_frame
        self.port.write(payload)

    def get_frame(self):
        """
        A simple function for getting message frame (json) from module,
        and return a Python object that is decoded from the message
        """
        # setting timeout value
        expect_end = None
        if self.timeout and (self.timeout > -1):
            expect_end = time.time() + self.timeout

        # getting the start point of a frame
        char = self.port.read()
        while char != self.start_of_frame:
            if expect_end and (expect_end <= time.time()):
                logging.debug("LMP %s : get_frame times out: CAN'T get the START of a frame" % self.serialno)
                return None
            char = self.port.read()

        response = ""

        # read until the end point of a frame
        while char != self.end_of_frame:
            if expect_end and (expect_end <= time.time()):
                logging.debug("LMP: Got a incomplete frame: %s" % response)
                logging.debug("LMP %s : get_frame times out: CAN'T get the END of a frame" % self.serialno)
                return None
            char = self.port.read()
            if char != self.end_of_frame and char != "\n" and char != "\r":
                response += char

        logging.debug("LMP: Got %s" % response)

        # return a Python object
        return json.loads(response)

    def get_response(self, schema):
        """
        Getting the feedback message from module.
        It's a wrapper of get_frame.
        :param schema: to specify the message type ["board", "report"] we want
        :return a Python object that is decoded from the message
        """
        got_schema = False
        get_response_retry = self.retry
        response_wanted = "org.linaro.lmp." + schema
        logging.debug("LMP: wanted %s" % response_wanted)

        while not got_schema:
            self.port.flushInput()
            if self.need_info_trigger is True or schema == "board":
                self.send_frame('{"schema":"org.linaro.lmp.info"}')

            result = self.get_frame()
            if result is not None and \
                    'schema' in result and \
                    schema == "report" and \
                    result['schema'] == "org.linaro.lmp.board":
                result = self.get_frame()

            if result is not None and \
                    'schema' in result and \
                    result['schema'] == response_wanted:
                got_schema = True
                logging.debug("LMP: Response is matched %s" % response_wanted)
            else:
                get_response_retry -= 1
                if get_response_retry <= 0:
                    self.set_identify()
                    raise CriticalError("LMP %s %s may need to re-connect to LAVA server!" % (self.board_type, serial))
                else:
                    logging.error("LMP: Fail to get response: %s, retry %s..." % (schema, get_response_retry))

        return result

    def set_identify(self, identify=True):
        """
        Set the identify LED1, so you can find it.
        :param identify: to specify the identify status we want
        """
        if identify is True:
            message = '{"schema":"org.linaro.lmp.base", "identify":true}'
        else:
            message = '{"schema":"org.linaro.lmp.base", "identify":false}'
        self.send_frame(message)

    def software_reset(self, reset_value=False):
        """
        Software reset LMP module by serial port.
        :param reset_value: to specify the reset status we want
        """
        if reset_value is True:
            message = '{"schema":"org.linaro.lmp.base", "reset":true}'
        else:
            message = '{"schema":"org.linaro.lmp.base", "reset":false}'
        self.send_frame(message)

    def send_command(self, mode, selection):
        """
        Send command to module and getting the feedback message. It's a wrapper of send_frame.
        If self.need_check_mode is set, it will check the result until the module get into the right mode.
        :param mode: the mode we want to set
        :param selection: the value of the mode
        :return a Python object that is decoded from the feedback message
        """
        message = '{"schema":"' + self.lmp_type_stream + '",' + \
            '"serial":"' + self.serialno + '",' + \
            '"modes":[{"name":"' + mode + '",' + \
            '"option":"' + selection + '"}]}'

        self.send_frame(message)

        if self.need_check_mode is True:
            response = self.check_mode(mode, selection)
        else:
            response = self.get_response("report")

        return response

    def send_multi_command(self, mode_selection_dict):
        """
        Send multi commands to module and getting the feedback message. It's a wrapper of send_frame.
        :param mode_selection_dict: {mode_1: selection_1, mode_2: selection_2} we want to set
        :return a Python object that is decoded from the feedback message
        """
        modes_stream = ''
        for name, option in mode_selection_dict.items():
            modes_stream += '{"name":"' + name + '",' + '"option":"' + option + '"},'

        message = '{"schema":"' + self.lmp_type_stream + '",' + \
            '"serial":"' + self.serialno + '",' + \
            '"modes":[' + modes_stream[0:-1] + ']}'

        self.send_frame(message)

        response = self.get_response("report")

        return response

    def check_mode(self, name, mode):
        """
        Checking the mode value from the feedback message of module,
        and return a Python object that is decoded from the "report" message.
        SOME of module types can use the func:
         SD MUX
         ETH+STAT
        """
        # TODO: ADD the retry time and the command re-send function

        device_in_mode = False

        while not device_in_mode:
            try:
                response = self.get_response("report")
            except ValueError as e:
                logging.warning("LMP Frame read error: %s" % e)
                continue
            else:
                for i in response["report"]:
                    if i["name"] == "modes":
                        modes = dict(i)
                        for j in modes["modes"]:
                            state = dict(j)
                            if state["name"] == name and state["mode"] == mode:
                                logging.debug("LMP %s: %s now is in mode %s" % (self.board_type, name, mode))
                                device_in_mode = True

        return response

    def close(self):
        """ A simple function for disconnecting with module
        """
        self.port.close()


def lmp_send_command(serial, lmp_type, mode, state, need_check_mode=False):
    """
    Helper function for sending a single command to a LMP module
    :param serial: serial number of the module set
    :param lmp_type: to specify the module we want operate
    :param mode & state: to specify the command
    :param need_check_mode(option): if we need to check the response
    :return a Python object that is decoded from the feedback message
    """
    lmp = LAVALmpDeviceSerial(serial, lmp_type, need_check_mode)
    response = lmp.send_command(mode, state)
    lmp.close()
    return response


def lmp_send_multi_command(serial, lmp_type, mode_selection_dict, need_check_mode=False):
    """
    Helper function for sending a single command to a LMP module
    :param serial: serial number of the module set
    :param lmp_type: to specify the module we want operate
    :param mode_selection_dict: {mode_1: selection_1, mode_2: selection_2}
    :param need_check_mode(option): if we need to check the response
    :return a Python object that is decoded from the feedback message
    """
    lmp = LAVALmpDeviceSerial(serial, lmp_type, False)
    response = lmp.send_multi_command(mode_selection_dict)
    lmp.close()
    return response


def lmp_set_identify(serial, lmp_type, identify=True):
    """
    Helper function for sending a single command to a LMP module
    :param serial: serial number of the module set
    :param lmp_type: to specify the module we want operate
    :param identify(option): Bool
    :return a Python object that is decoded from the feedback message
    """
    lmp = LAVALmpDeviceSerial(serial, lmp_type, False)
    lmp.set_identify(identify)
    lmp.close()
    return None


def lmp_reset(serial, lmp_type, reset_value=False):
    """
    Helper function for sending a single command to a LMP module
    :param serial: serial number of the module set
    :param lmp_type: to specify the module we want operate
    :param reset_value(option): Bool
    :return a Python object that is decoded from the feedback message
    """
    lmp = LAVALmpDeviceSerial(serial, lmp_type, False)
    lmp.software_reset(reset_value)
    lmp.close()
    return None


def get_one_of_report(response, name=None):
    """
    A simple helper function for getting one of report
    :param response: a report Python object
    :param name: to specify the report name we want
    :return a Python object that is decoded from the feedback message
    """
    if name is None:
        return response
    else:
        for i in response["report"]:
            if i["name"] == name:
                return dict(i)
    return None


def get_module_serial(lmp_id, module_name, config):
    if not module_name or module_name == config.lmp_default_name:
        module_name = config.lmp_default_name
        if not lmp_id or module_name not in lmp_id:
            return config.lmp_default_id
        else:
            return lmp_id[module_name]
    else:
        if lmp_id and module_name in lmp_id:
            return lmp_id[module_name]
        else:
            logging.error("Can not get LMP module ID!")
            return None
