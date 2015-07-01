#!/usr/bin/python

# Copyright (C) 2011 Linaro Limited
#
# Author: Paul Larson <paul.larson@linaro.org>
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

from lava_dispatcher.actions import BaseAction, null_or_empty_schema
from lava_dispatcher.errors import (
    CriticalError,
    ADBConnectError,
)

_boot_schema = {
    'type': 'object',
    'properties': {
        'options': {'type': 'array', 'items': {'type': 'string'},
                    'optional': True},
        'boot_cmds': {'type': 'array', 'items': {'type': 'string'},
                      'optional': True},
        'sim_options': {'type': 'array', 'items': {'type': 'string'},
                        'optional': True},
        'role': {'type': 'string', 'optional': True},
        'repeat': {'type': 'integer', 'optional': True},
        'repeat_count': {'type': 'integer', 'optional': True},
    },
    'additionalProperties': False,
}


class cmd_boot_linaro_android_image(BaseAction):
    """ Call client code to boot to the master image
    """

    parameters_schema = _boot_schema
    parameters_schema['properties']['adb_check'] = {
        'default': False, 'optional': True
    }
    parameters_schema['properties']['wait_for_home_screen'] = {
        'default': False, 'optional': True
    }
    parameters_schema['properties']['wait_for_home_screen_activity'] = {
        'type': 'string', 'optional': True
    }
    parameters_schema['properties']['test_image_prompt'] = {
        'type': 'string', 'optional': True
    }
    parameters_schema['properties']['interrupt_boot_prompt'] = {
        'type': 'string', 'optional': True
    }
    parameters_schema['properties']['enable_network_after_boot_android'] = {
        'default': 'True', 'optional': True
    }
    parameters_schema['properties']['boot_uiautomator_jar'] = {
        'type': 'string', 'optional': True
    }
    parameters_schema['properties']['boot_uiautomator_commands'] = {
        'type': 'array', 'items': {'type': 'string'}, 'optional': True
    }

    def run(self, options=[], boot_cmds=None, sim_options=None, adb_check=False,
            wait_for_home_screen=True, wait_for_home_screen_activity=None,
            test_image_prompt=None, interrupt_boot_prompt=None,
            enable_network_after_boot_android=None, repeat_count=0,
            boot_uiautomator_jar=None, boot_uiautomator_commands=None):
        client = self.client
        if boot_cmds is not None:
            client.config.boot_cmds = boot_cmds
        if sim_options is not None:
            client.config.simulator_options = sim_options
        if wait_for_home_screen_activity is not None:
            client.config.android_wait_for_home_screen_activity = \
                wait_for_home_screen_activity
        if test_image_prompt is not None:
            test_image_prompts = client.config.test_image_prompts
            test_image_prompts.append(test_image_prompt)
            client.config.test_image_prompts = test_image_prompts
        if interrupt_boot_prompt is not None:
            client.config.interrupt_boot_prompt = interrupt_boot_prompt
        if enable_network_after_boot_android is not None:
            client.config.enable_network_after_boot_android = \
                enable_network_after_boot_android
        client.target_device.boot_options = options
        client.config.android_wait_for_home_screen = wait_for_home_screen
        client.target_device.reset_boot(in_test_shell=False)
        client.config.android_boot_uiautomator_jar = \
            boot_uiautomator_jar
        client.config.android_boot_uiautomator_commands = \
            boot_uiautomator_commands
        try:
            client.boot_linaro_android_image(
                adb_check=adb_check)
        except ADBConnectError as err:
            logging.exception('boot_linaro_android_image failed to create'
                              ' the adb connection: %s', err)
            raise err
        except Exception as e:
            logging.exception("boot_linaro_android_image failed: %s", e)
            raise CriticalError("Failed to boot test image.")


cmd_boot_android_image = cmd_boot_linaro_android_image


class cmd_boot_linaro_image(BaseAction):
    """ Call client code to boot to the test image
    """

    parameters_schema = _boot_schema
    parameters_schema['properties']['test_image_prompt'] = {
        'type': 'string', 'optional': True
    }
    parameters_schema['properties']['interrupt_boot_prompt'] = {
        'type': 'string', 'optional': True
    }

    def run(self, options=[], boot_cmds=None, sim_options=None, test_image_prompt=None,
            interrupt_boot_prompt=None, repeat_count=0):
        client = self.client
        if boot_cmds is not None:
            client.config.boot_cmds = boot_cmds
        if sim_options is not None:
            client.config.simulator_options = sim_options
        if test_image_prompt is not None:
            test_image_prompts = client.config.test_image_prompts
            test_image_prompts.append(test_image_prompt)
            client.config.test_image_prompts = test_image_prompts
        if interrupt_boot_prompt is not None:
            client.config.interrupt_boot_prompt = interrupt_boot_prompt
        client.target_device.boot_options = options
        client.target_device.reset_boot(in_test_shell=False)
        status = 'pass'
        try:
            client.boot_linaro_image()
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except:
            status = 'fail'
            raise CriticalError("Failed to boot test image.")


cmd_boot_image = cmd_boot_linaro_image


class cmd_boot_master_image(BaseAction):
    """ Call client code to boot to the master image
    """

    parameters_schema = null_or_empty_schema

    def run(self):
        client = self.client
        client.boot_master_image()
