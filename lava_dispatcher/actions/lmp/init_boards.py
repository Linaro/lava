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


def data_integrate(lmp_module_data, config):
    # convert config date to lmp_module_data format
    lmp_module_data_integrated = []
    if config.lmp_hdmi_defconf is not None:
        for module_name, module_defconf in config.lmp_hdmi_defconf.items():
            module_init_item = {'hdmi': module_defconf, 'parameters': {'name': module_name}}
            lmp_module_data_integrated.append(module_init_item)
    if config.lmp_sata_defconf is not None:
        for module_name, module_defconf in config.lmp_sata_defconf.items():
            module_init_item = {'sata': module_defconf, 'parameters': {'name': module_name}}
            lmp_module_data_integrated.append(module_init_item)
    if config.lmp_eth_defconf is not None:
        for module_name, module_defconf in config.lmp_eth_defconf.items():
            module_init_item = {'eth': module_defconf, 'parameters': {'name': module_name}}
            lmp_module_data_integrated.append(module_init_item)
    if config.lmp_lsgpio_defconf is not None:
        for module_name, module_defconf in config.lmp_lsgpio_defconf.items():
            module_init_item = {'lsgpio': module_defconf, 'parameters': {'name': module_name}}
            lmp_module_data_integrated.append(module_init_item)
    if config.lmp_audio_defconf is not None:
        for module_name, module_defconf in config.lmp_audio_defconf.items():
            module_init_item = {'audio': module_defconf, 'parameters': {'name': module_name}}
            lmp_module_data_integrated.append(module_init_item)
    if config.lmp_usb_defconf is not None:
        for module_name, module_defconf in config.lmp_usb_defconf.items():
            module_init_item = {'usb': module_defconf, 'parameters': {'name': module_name}}
            lmp_module_data_integrated.append(module_init_item)

    logging.debug("lmp modules default init data is %s", lmp_module_data_integrated.__str__())

    # overlay lmp_module_data onto default config data
    for lmp_module_element in lmp_module_data:
        # get module_name first
        if 'parameters' in lmp_module_element and\
           'name' in lmp_module_element['parameters']:
            module_name = lmp_module_element['parameters']['name']
        else:
            module_name = config.lmp_default_name
        # get module_type
        for key_string in lmp_module_element.keys():
            if key_string in ['hdmi', 'sata', 'eth', 'lsgpio', 'audio', 'usb']:
                module_type = key_string
                module_defconf = lmp_module_element[module_type]
        logging.debug("lmp %s module %s init data is %s",
                      module_type, module_name, module_defconf)
        # poll the default config data of LMP, overlay the default config by initial data in the job definition
        for lmp_module_data_integrated_item in lmp_module_data_integrated:
            if module_type in lmp_module_data_integrated_item:
                logging.debug("__match lmp %s module type__", module_type)
                if lmp_module_data_integrated_item['parameters']['name'] == module_name:
                    logging.debug("init lmp %s module %s as %s(overlay %s)",
                                  module_type, module_name, module_defconf,
                                  lmp_module_data_integrated_item[module_type])
                    lmp_module_data_integrated_item[module_type] = module_defconf

    logging.debug("lmp modules final init data is %s", lmp_module_data_integrated.__str__())

    # return
    return lmp_module_data_integrated


# init LMP module
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
