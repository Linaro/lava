# Copyright (C) 2014 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from typing import Any


def substitute(
    command_list: Iterable[str],
    dictionary: Mapping[str, str | None],
    drop: bool = False,
    drop_line: bool = True,
) -> list[str]:
    """
    Replace markup in the command_list which matches a key in the dictionary with the
    value of that key in the dictionary. Empty values leave the item unchanged.
    Markup needs to be safe to use in the final command as there is no guarantee that
    any dictionary will replace all markup in the command_list.
    arguments: command_list - a list of strings
               dictionary - a dictionary of keys which match some of the strings with values
                            to replace for the key in the string.
               drop - drop the value if a key is present but the value is None/empty
               drop_line - drop the entire command if a key is present but the value is None/empty
    """
    parsed: list[str] = []

    def process_line(line: str) -> None:
        for key, value in dictionary.items():
            if value:
                line = line.replace(key, value)
            elif drop and key in line:
                # If drop_line is activated or Value=None, remove the entire line
                if drop_line or value is None:
                    return
                else:  # Otherwise, replace just the key by nothing
                    line = line.replace(key, value)

        parsed.append(line)

    for line in command_list:
        process_line(line)

    return parsed


def substitute_address_with_static_info(
    address: str, static_info: Iterable[Mapping[str, str | None]]
) -> str:
    substitutions: dict[str, str | None] = {
        "{" + k + "}": v for info in static_info for (k, v) in info.items()
    }
    return substitute([address], substitutions)[0]


def seconds_to_str(time: float) -> str:
    hours, remainder = divmod(int(round(time)), 3600)
    minutes, seconds = divmod(remainder, 60)
    return "%02d:%02d:%02d" % (hours, minutes, seconds)


def safe_dict_format(string: str, dictionary: dict[str, str]) -> str:
    """
    Used to replace value in string using dictionary
    eg : '{foo}{bar}.safe_dict_format({'foo' : 'hello'})
    >>> 'hello{bar}'
    """

    class SafeDict(dict[str, str]):
        def __missing__(self, key: str) -> str:
            logger = logging.getLogger("dispatcher")
            logger.warning("Missing key : '{%s}' for string '%s'", key, string)
            return "{" + key + "}"

    return string.format_map(SafeDict(dictionary))


def map_kernel_uboot(
    kernel_type: str, device_params: dict[str, Any] | None = None
) -> str:
    """
    Support conversion of kernels only if the device cannot
    handle what has been given by the test job writer.

    Decide based on the presence of suitable load addresses.
    If deploy gets a kernel type for which there is no matching boot kernel address
    then if a bootm address exists do the conversion.
    bootm is the last resort.
    """
    bootcommand = "bootm"
    logger = logging.getLogger("dispatcher")
    if kernel_type == "uimage":
        return bootcommand
    elif kernel_type == "zimage":
        if device_params and "bootz" in device_params:
            bootcommand = "bootz"
        else:
            logger.warning(
                "No bootz parameters available, falling back to bootm and converting zImage"
            )
    elif kernel_type == "image":
        if device_params and "booti" in device_params:
            bootcommand = "booti"
        else:
            logger.warning(
                "No booti parameters available, falling back to bootm and converting zImage"
            )
    return bootcommand
