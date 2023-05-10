# Copyright (C) 2014 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
import logging


def indices(string, char):
    """
    Return the indices of the given character in the given string.
    Return an empty list if the character cannot be found.
    """
    return [i for i, c in enumerate(string) if c == char]


def substitute(command_list, dictionary, drop=False, drop_line=True):
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
    parsed = []
    for line in command_list:
        for key, value in dictionary.items():
            if value:
                line = line.replace(key, value)
            elif drop and key in line:
                # If drop_line is activated or Value=None, remove the entire line
                if drop_line or value is None:
                    line = None
                    break
                # Otherwise, replace just the key by nothing
                else:
                    line = line.replace(key, value)
        if line is not None:
            parsed.append(line)
    return parsed


def seconds_to_str(time):
    hours, remainder = divmod(int(round(time)), 3600)
    minutes, seconds = divmod(remainder, 60)
    return "%02d:%02d:%02d" % (hours, minutes, seconds)


def safe_dict_format(string, dictionary):
    """
    Used to replace value in string using dictionary
    eg : '{foo}{bar}.safe_dict_format({'foo' : 'hello'})
    >>> 'hello{bar}'
    """

    class SafeDict(dict):
        def __missing__(self, key):
            logger = logging.getLogger("lava-dispatcher")
            logger.warning("Missing key : '{%s}' for string '%s'", key, string)
            return "{" + key + "}"

    return string.format_map(SafeDict(dictionary))


def map_kernel_uboot(kernel_type, device_params=None):
    """
    Support conversion of kernels only if the device cannot
    handle what has been given by the test job writer.

    Decide based on the presence of suitable load addresses.
    If deploy gets a kernel type for which there is no matching boot kernel address
    then if a bootm address exists do the conversion.
    bootm is the last resort.
    """
    bootcommand = "bootm"
    logger = logging.getLogger("lava-dispatcher")
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
