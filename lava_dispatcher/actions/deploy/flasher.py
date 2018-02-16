# Copyright (C) 2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
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

import yaml

from lava_dispatcher.action import Pipeline, JobError
from lava_dispatcher.actions.deploy import DeployAction
from lava_dispatcher.actions.deploy.download import DownloaderAction
from lava_dispatcher.actions.deploy.environment import DeployDeviceEnvironment
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.logical import Deployment
from lava_dispatcher.utils.strings import substitute


class FlasherAction(DeployAction):

    def __init__(self):
        super(FlasherAction, self).__init__()
        self.name = "deploy-flasher"
        self.description = "deploy flasher"
        self.summary = "deploy custom flasher"
        self.commands = []
        self.path = None

    def validate(self):
        super(FlasherAction, self).validate()
        method = self.job.device['actions']['deploy']['methods']['flasher']
        self.commands = method.get("commands")
        if not isinstance(self.commands, list):
            self.errors = "'commands' should be a list"

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)

        # Download the images
        self.path = self.mkdtemp()
        for image in [key for key in parameters['images'].keys() if key != "yaml_line"]:
            self.internal_pipeline.add_action(DownloaderAction(image, self.path))

        if self.test_needs_deployment(parameters):
            self.internal_pipeline.add_action(DeployDeviceEnvironment())
        if self.test_needs_overlay(parameters):
            self.internal_pipeline.add_action(OverlayAction())

    def run(self, connection, max_end_time, args=None):
        connection = super(FlasherAction, self).run(connection, max_end_time, args)
        # Substitute in the device commands
        substitutions = {}
        for key in [key for key in self.parameters['images'].keys() if key != "yaml_line"]:
            filename = self.get_namespace_data(action='download-action', label=key, key='file')
            filename = filename[len(self.path) + 1:]
            substitutions["{%s}" % key.upper()] = filename

        # Add power commands
        substitutions["{HARD_RESET_COMMAND}"] = self.job.device.hard_reset_command
        substitutions["{SOFT_RESET_COMMAND}"] = self.job.device.soft_reset_command
        substitutions["{PRE_OS_COMMAND}"] = self.job.device.pre_os_command
        if substitutions["{PRE_OS_COMMAND}"] is None:
            substitutions["{PRE_OS_COMMAND}"] = ''
        substitutions["{PRE_POWER_COMMAND}"] = self.job.device.pre_power_command
        if substitutions["{PRE_POWER_COMMAND}"] is None:
            substitutions["{PRE_POWER_COMMAND}"] = ''
        substitutions["{POWER_ON_COMMAND}"] = self.job.device.power_command
        substitutions["{POWER_OFF_COMMAND}"] = self.job.device.get('commands', {}).get('power_off', '')

        # Add some device configuration
        substitutions["{DEVICE_INFO}"] = yaml.dump(self.job.device.get("device_info", []))
        substitutions["{STATIC_INFO}"] = yaml.dump(self.job.device.get("static_info", []))

        # Run the commands
        for cmd in self.commands:
            cmds = substitute(cmd.split(" "), substitutions)
            if not self.run_command(cmds, allow_fail=False, allow_silent=True, cwd=self.path):
                raise JobError("Unable to flash the device")

        return connection


class Flasher(Deployment):
    compatibility = 4
    name = 'flasher'

    def __init__(self, parent, parameters):
        super(Flasher, self).__init__(parent)
        self.action = FlasherAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if 'flasher' not in device['actions']['deploy']['methods']:
            return False, "'flasher' not in the device configuration deploy methods"
        if parameters['to'] != 'flasher':
            return False, '"to" parameter is not "flasher"'
        return True, 'accepted'
