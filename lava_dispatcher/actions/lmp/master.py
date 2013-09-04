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

import serial
import json
import logging
from serial import (
    serialutil
)
from lava_dispatcher.errors import (
    CriticalError,
)

class LAVALmpDeviceSerial(object):
    def __init__(self, serialno, board_type):
        device_map = {
            "sdmux": "0a",
            "sata": "19",
            "lsgpio": "09",
            "hdmi": "0c",
            "usb": "04"
        }
        self.serialno = "LL" + device_map[board_type] + serialno.zfill(12)
        logging.debug("LMP Serial #: %s" % self.serialno)
        self.lmpType = "org.linaro.lmp." + board_type
        self.board_type = board_type
        try:
            self.port = serial.Serial("/dev/serial/by-id/usb-Linaro_Ltd_LavaLMP_" + self.serialno + "-if00", timeout=1)
        except serial.serialutil.SerialException as e:
            logging.error("LMP: Error opening {0:s}: {1:s}".format(self.serialno, e))
            raise
        self.START_FRAME = '\x02'
        self.END_FRAME = '\x04'
        self.sendFrame('{"schema":"org.linaro.lmp.info"}')
        message = self.getResponse("board")
        if message['serial'] != self.serialno:
            raise CriticalError("Lmp %s not connected" % serial)

    def sendCommand(self, mode, selection):
        message = '{"schema":"' + self.lmpType + '",' + \
            '"serial":"' + self.serialno + '",' + \
            '"modes":[{"name":"' + mode + '",' + \
            '"option":"' + selection + '"}]}'
        self.sendFrame(message)
        device_in_mode = False
        while not device_in_mode:
            try:
                response = self.getFrame()
            except ValueError as e:
                logging.warning("LMP Frame read error: %s" % e)
                continue
            else:
                for i in response["report"]:
                    if i["name"] == "modes":
                        modes = dict(i)
                        for j in modes["modes"]:
                            state = dict(j)
                            if state["name"] == mode and state["mode"] == selection:
                                logging.debug("LMP %s: %s now in mode %s" % (self.board_type, mode, selection))
                                device_in_mode = True

    def sendFrame(self, command):
        logging.debug("LMP: Sending %s" % command)
        payload = self.START_FRAME + command + self.END_FRAME
        self.port.write(payload)

    def getResponse(self, schema):
        got_schema = False

        result = self.getFrame()

        while not got_schema:
            if result['schema'] == "org.linaro.lmp." + schema:
                got_schema = True
            else:
                result = self.getFrame()

        return result

    def getFrame(self):
        char = self.port.read()

        while char != self.START_FRAME:
            char = self.port.read()

        response = ""

        while char != self.END_FRAME:
            char = self.port.read()
            if char != self.END_FRAME:
                response += char

        logging.debug("LMP: Got %s" % response)

        return json.loads(response)

    def close(self):
        self.port.close()


def lmp_send_command(serial, lmp_type, mode, state):
    lmp = LAVALmpDeviceSerial(serial, lmp_type)
    lmp.sendCommand(mode, state)
    lmp.close()
