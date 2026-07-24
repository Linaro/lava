# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from yaml import YAMLError

from lava_common.exceptions import ConfigurationError
from lava_common.yaml import yaml_safe_load

if TYPE_CHECKING:
    from pathlib import Path


class DeviceDict(dict[str, Any]):
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

    @staticmethod
    def _coerce_command(value: Any) -> str | list[str]:
        if value is None:
            return ""
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, list):
            return value
        return str(value)

    @property
    def hard_reset_command(self) -> str | list[str]:
        return self._coerce_command(self.get("commands", {}).get("hard_reset", ""))

    @property
    def soft_reboot_command(self) -> str | list[str]:
        return self._coerce_command(self.get("commands", {}).get("soft_reboot", ""))

    @property
    def pre_os_command(self) -> str | list[str] | None:
        value = self.get("commands", {}).get("pre_os_command")
        if value is None:
            return None
        return self._coerce_command(value)

    @property
    def pre_power_command(self) -> str | list[str] | None:
        value = self.get("commands", {}).get("pre_power_command")
        if value is None:
            return None
        return self._coerce_command(value)

    @property
    def power_command(self) -> str | list[str]:
        return self._coerce_command(self.get("commands", {}).get("power_on", ""))

    @property
    def connect_command(self) -> str:
        if "commands" not in self:
            raise ConfigurationError(
                "commands section not present in the device config."
            )
        if "connect" in self["commands"]:
            return str(self["commands"]["connect"])
        elif "connections" in self["commands"]:
            for value in self["commands"]["connections"].values():
                if "connect" not in value:
                    return ""
                if "tags" in value and "primary" in value["tags"]:
                    return str(value["connect"])
        return ""

    def get_constant(
        self,
        const: str,
        prefix: str | None = None,
        missing_ok: bool = False,
        missing_default: Any | None = None,
    ) -> Any:
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
