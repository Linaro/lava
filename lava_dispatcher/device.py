# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import yaml

from lava_common.exceptions import ConfigurationError
from lava_common.yaml import yaml_safe_load


class PipelineDevice(dict):
    """
    Dictionary Device class which accepts data rather than a filename.
    This allows the scheduler to use the same class without needing to write
    out YAML files from database content.
    """

    def __init__(self, config):
        super().__init__()
        self.update(config)

    def check_config(self, job):
        """
        Validates the combination of the job and the device
        *before* the Deployment actions are initialised.
        """
        raise NotImplementedError("check_config")

    @property
    def hard_reset_command(self):
        return self.get("commands", {}).get("hard_reset", "")

    @property
    def soft_reboot_command(self):
        return self.get("commands", {}).get("soft_reboot", "")

    @property
    def pre_os_command(self):
        return self.get("commands", {}).get("pre_os_command")

    @property
    def pre_power_command(self):
        return self.get("commands", {}).get("pre_power_command")

    @property
    def power_command(self):
        return self.get("commands", {}).get("power_on", "")

    @property
    def connect_command(self):
        if "commands" not in self:
            raise ConfigurationError(
                "commands section not present in the device config."
            )
        if "connect" in self["commands"]:
            return self["commands"]["connect"]
        elif "connections" in self["commands"]:
            for hardware, value in self["commands"]["connections"].items():
                if "connect" not in value:
                    return ""
                if "tags" in value and "primary" in value["tags"]:
                    return value["connect"]
        return ""

    def get_constant(self, const, prefix=None, missing_ok=False, missing_default=None):
        if "constants" not in self:
            raise ConfigurationError(
                "constants section not present in the device config."
            )
        constants = self["constants"]
        if prefix:
            if prefix in constants:
                if const in constants[prefix]:
                    return constants[prefix][const]
            if missing_ok:
                return missing_default
            raise ConfigurationError(
                "Constant %s,%s does not exist in the device config 'constants' section."
                % (prefix, const)
            )
        if const in constants:
            return constants[const]
        if missing_ok:
            return missing_default
        raise ConfigurationError(
            "Constant %s does not exist in the device config 'constants' section."
            % const
        )


class NewDevice(PipelineDevice):
    """
    YAML based PipelineDevice class with clearer support for the pipeline overrides
    and deployment types. Simple change of init whilst allowing the scheduler and
    the dispatcher to share the same functionality.
    """

    def __init__(self, target):
        super().__init__({})
        # Parse the yaml configuration
        try:
            if isinstance(target, str):
                with open(target) as f_in:
                    data = f_in.read()
                data = yaml_safe_load(data)
            elif isinstance(target, dict):
                data = target
            else:
                data = target.read()
                data = yaml_safe_load(data)
            if data is None:
                raise ConfigurationError("Missing device configuration")
            self.update(data)
        except yaml.parser.ParserError:
            raise ConfigurationError("%s could not be parsed" % target)

        self.setdefault("power_state", "off")  # assume power is off at start of job
        self.setdefault("dynamic_data", {})

    def check_config(self, job):
        """
        Validates the combination of the job and the device
        *before* the Deployment actions are initialised.
        """
        raise NotImplementedError("check_config")
