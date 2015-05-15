# Copyright (C) 2015 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
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

import os
import yaml

from lava_dispatcher.pipeline.action import Action


class DeployDeviceEnvironment(Action):
    """
    Create environment found in job parameters 'env_dut' and set it in common_data.
    """

    def __init__(self):
        super(DeployDeviceEnvironment, self).__init__()
        self.name = "deploy-device-env"
        self.summary = "deploy device environment"
        self.description = "deploy device environment"
        self.env = ""

    def validate(self):
        if 'lava_test_shell_file' not in \
           self.parameters['deployment_data'].keys():
            self.errors = "Invalid deployment data - missing lava_test_shell_file"
        if self.job.parameters['env_dut']:
            try:
                yaml.load(self.job.parameters['env_dut'])
            except (TypeError, yaml.scanner.ScannerError) as exc:
                self.errors = exc
                return

        if 'env_dut' in self.job.parameters and self.job.parameters['env_dut']:

            self.env = self.job.parameters['env_dut']
            environment = self._create_environment()

            self.set_common_data(
                'environment',
                'shell_file',
                self.parameters['deployment_data']['lava_test_shell_file'])

            self.set_common_data(
                'environment',
                'env_dict',
                environment)

        else:
            self.logger.info("no device environment specified")

    def _create_environment(self):
        """Generate the env variables for the device."""
        conf = yaml.load(self.env) if self.env is not '' else {}
        if conf.get("purge", False):
            environ = {}
        else:
            environ = dict(os.environ)

        # Remove some variables (that might not exist)
        for var in conf.get("removes", {}):
            try:
                del environ[var]
            except KeyError:
                pass

        # Override
        environ.update(conf.get("overrides", {}))
        return environ
