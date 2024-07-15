# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING

from yaml import YAMLError

from lava_common.exceptions import ConfigurationError
from lava_common.yaml import yaml_safe_load

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any


class DeviceDict(dict):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.setdefault("power_state", "off")  # assume power is off at start of job
        self.setdefault("dynamic_data", {})

    @classmethod
    def from_yaml_str(cls, yaml_str: str) -> DeviceDict:
        try:
            data = yaml_safe_load(yaml_str)
        except YAMLError as exc:
            raise ConfigurationError("Device dict could not be parsed") from exc

        if data is None:
            raise ConfigurationError("Empty device configuration")

        return cls(**data)

    @classmethod
    def from_path(cls, path: str | Path) -> DeviceDict:
        with open(path) as f:
            return cls.from_yaml_str(f.read())

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
                f"Constant {prefix},{const} does not exist in the device "
                "config 'constants' section."
            )
        if const in constants:
            return constants[const]
        if missing_ok:
            return missing_default
        raise ConfigurationError(
            "Constant %s does not exist in the device config 'constants' section."
            % const
        )
