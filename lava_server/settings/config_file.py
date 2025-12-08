# Copyright (C) 2013-2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""
Simple shell-sourcable configuration file class
"""
from __future__ import annotations

from shlex import split as shlex_split
from typing import TYPE_CHECKING
from warnings import warn

if TYPE_CHECKING:
    from pathlib import Path


class ConfigFile:
    """
    Configuration file parser compatible with files generated
    dbconfig-generate-include using sh format.
    """

    @staticmethod
    def load(pathname: str | Path) -> dict[str, str]:
        """
        Load file from pathname and store all the values as instance attributes
        """
        config: dict[str, str] = {}
        for lineno, line in enumerate(open(pathname)):
            parsed_tokens = shlex_split(line, comments=True)
            if not parsed_tokens:
                # Skip empty lines
                continue

            try:
                key, value = parsed_tokens[0].split("=", maxsplit=1)
            except (ValueError, IndexError):
                warn(f"Failed to parse line {lineno} in file {pathname}: {line}")
                continue

            config[key] = value
        return config
