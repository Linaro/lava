# Copyright (C) 2015 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import contextlib
import os

import yaml

from lava_common.constants import LINE_SEPARATOR
from lava_common.yaml import yaml_safe_load
from lava_dispatcher.action import Action


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
        shell_file = self.get_constant("lava_test_shell_file", "posix")
        if not shell_file:
            self.errors = "Invalid deployment data - missing lava_test_shell_file"

        if "env_dut" in self.job.parameters and self.job.parameters["env_dut"]:
            # Check that the file is valid yaml
            try:
                yaml_safe_load(self.job.parameters["env_dut"])
            except (TypeError, yaml.scanner.ScannerError) as exc:
                self.errors = exc
                return

            self.env = self.job.parameters["env_dut"]
            environment = self._create_environment()

            self.set_namespace_data(
                action=self.name,
                label="environment",
                key="shell_file",
                value=shell_file,
            )

            self.set_namespace_data(
                action=self.name, label="environment", key="env_dict", value=environment
            )

        self.set_namespace_data(
            action=self.name,
            label="environment",
            key="line_separator",
            value=self.parameters["deployment_data"].get(
                "line_separator", LINE_SEPARATOR
            ),
        )

    def _create_environment(self):
        """Generate the env variables for the device."""
        conf = yaml_safe_load(self.env) if self.env != "" else {}
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
