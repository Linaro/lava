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

import contextlib
import os
import yaml

from lava_dispatcher.action import Action
from lava_common.constants import LINE_SEPARATOR


class DeployDeviceEnvironment(Action):
    """
    Create environment found in job parameters 'env_dut' and set it in common_data.
    """

    name = "deploy-device-env"
    description = "deploy device environment"
    summary = "deploy device environment"

    def __init__(self):
        super().__init__()
        self.env = ""

    def validate(self):
        super().validate()
        shell_file = self.get_constant('lava_test_shell_file', 'posix')
        if not shell_file:
            self.errors = "Invalid deployment data - missing lava_test_shell_file"

        if 'env_dut' in self.job.parameters and self.job.parameters['env_dut']:
            # Check that the file is valid yaml
            try:
                yaml.safe_load(self.job.parameters['env_dut'])
            except (TypeError, yaml.scanner.ScannerError) as exc:
                self.errors = exc
                return

            self.env = self.job.parameters['env_dut']
            environment = self._create_environment()

            self.set_namespace_data(
                action=self.name,
                label='environment',
                key='shell_file',
                value=self.parameters['deployment_data']['lava_test_shell_file']
            )

            self.set_namespace_data(
                action=self.name,
                label='environment',
                key='env_dict',
                value=environment
            )

        self.set_namespace_data(
            action=self.name,
            label='environment',
            key='line_separator',
            value=self.parameters['deployment_data'].get('line_separator', LINE_SEPARATOR)
        )

    def _create_environment(self):
        """Generate the env variables for the device."""
        conf = yaml.safe_load(self.env) if self.env != '' else {}
        if conf.get("purge", False):
            environ = {}
        else:
            environ = dict(os.environ)

        # Remove some variables (that might not exist)
        for var in conf.get("removes", {}):
            with contextlib.suppress(KeyError):
                del environ[var]

        # Override
        environ.update(conf.get("overrides", {}))
        return environ
