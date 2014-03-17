# Copyright (C) 2013 Linaro Limited
#
# Author: Fu Wei <fu.wei@linaro.org>
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

from json_schema_validator.schema import Schema
from json_schema_validator.validator import Validator

import lava_dispatcher.actions.lmp.eth as lmp_eth
import lava_dispatcher.actions.lmp.sata as lmp_sata
import lava_dispatcher.actions.lmp.hdmi as lmp_hdmi
import lava_dispatcher.actions.lmp.lsgpio as lmp_lsgpio
import lava_dispatcher.actions.lmp.usb as lmp_usb

from lava_dispatcher.actions.lmp.board import get_module_serial

lmp_module_schema = {
    'type': 'array',
    'additionalProperties': False,
    'optional': True,
    'items': {
        'type': 'object',
        'properties': {
            'usb': {
                'optional': True,
                'type': 'string',
            },
            'hdmi': {
                'optional': True,
                'type': 'string',
            },
            'eth': {
                'optional': True,
                'type': 'string',
            },
            'sata': {
                'optional': True,
                'type': 'string',
            },
            'audio': {
                'optional': True,
                'type': 'string',
            },
            'lsgpio': {
                'optional': True,
                'type': 'string',
            },
            'parameters': {
                'optional': True,
                'type': 'object',
            },
        },
    },
}


def _validate_lmp_module(lmp_module_data):
    schema = Schema(lmp_module_schema)
    Validator.validate(schema, lmp_module_data)


#init LMP module
def init(lmp_module_data, config):
    _validate_lmp_module(lmp_module_data)
    for lmp_module_element in lmp_module_data:
        if 'parameters' in lmp_module_element and\
           'name' in lmp_module_element['parameters']:
            module_name = lmp_module_element['parameters']['name']
        else:
            module_name = config.lmp_default_name

        if 'eth' in lmp_module_element:
            lmp_eth_id = get_module_serial(config.lmp_eth_id, module_name, config)
            logging.debug("lmp eth module %s init as %s"
                          % (lmp_eth_id,
                             lmp_module_element['eth']))
            if lmp_module_element['eth'] == "passthru":
                lmp_eth.passthru(lmp_eth_id)
            elif lmp_module_element['eth'] == "disconnect":
                lmp_eth.disconnect(lmp_eth_id)

        if 'sata' in lmp_module_element:
            lmp_sata_id = get_module_serial(config.lmp_sata_id, module_name, config)
            logging.debug("lmp sata module %s init as %s"
                          % (lmp_sata_id,
                             lmp_module_element['sata']))
            if lmp_module_element['sata'] == "passthru":
                lmp_sata.passthru(lmp_sata_id)
            elif lmp_module_element['sata'] == "disconnect":
                lmp_sata.disconnect(lmp_sata_id)

        if 'usb' in lmp_module_element:
            lmp_usb_id = get_module_serial(config.lmp_usb_id, module_name, config)
            logging.debug("lmp usb module %s init as %s"
                          % (lmp_usb_id,
                             lmp_module_element['usb']))
            if lmp_module_element['usb'] == "device":
                lmp_usb.device(lmp_usb_id)
            elif lmp_module_element['usb'] == "host":
                lmp_usb.host(lmp_usb_id)
            elif lmp_module_element['usb'] == "disconnect":
                lmp_usb.disconnect(lmp_usb_id)

        if 'hdmi' in lmp_module_element:
            lmp_hdmi_id = get_module_serial(config.lmp_hdmi_id, module_name, config)
            logging.debug("lmp hdmi module %s init as %s"
                          % (lmp_hdmi_id,
                             lmp_module_element['hdmi']))
            if lmp_module_element['hdmi'] == "passthru":
                lmp_hdmi.passthru(lmp_hdmi_id)
            elif lmp_module_element['hdmi'] == "disconnect":
                lmp_hdmi.disconnect(lmp_hdmi_id)

        if 'audio' in lmp_module_element:
            lmp_lsgpio_id = get_module_serial(config.lmp_lsgpio_id, module_name, config)
            logging.debug("lmp audio module %s init as %s"
                          % (lmp_lsgpio_id,
                             lmp_module_element['audio']))
            if lmp_module_element['audio'] == "passthru":
                lmp_lsgpio.audio_passthru(lmp_lsgpio_id)
            elif lmp_module_element['audio'] == "disconnect":
                lmp_lsgpio.audio_disconnect(lmp_lsgpio_id)

        if 'lsgpio' in lmp_module_element:
            lmp_lsgpio_id = get_module_serial(config.lmp_lsgpio_id, module_name, config)
            logging.debug("lmp lsgpio module %s init as %s"
                          % (lmp_lsgpio_id,
                             lmp_module_element['lsgpio']))
            if lmp_module_element['lsgpio'] == "a_in":
                lmp_lsgpio.a_dir_in(lmp_lsgpio_id)
            elif lmp_module_element['lsgpio'][:6] == "a_out_":
                lmp_lsgpio.a_data_out(lmp_lsgpio_id, lmp_module_element['lsgpio'][-2:])
            elif lmp_module_element['lsgpio'] == "b_in":
                lmp_lsgpio.b_dir_in(lmp_lsgpio_id)
            elif lmp_module_element['lsgpio'][:6] == "b_out_":
                lmp_lsgpio.b_data_out(lmp_lsgpio_id, lmp_module_element['lsgpio'][-2:])
