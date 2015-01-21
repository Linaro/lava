# Copyright (C) 2014 Linaro Limited
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


def indices(string, char):
    """
    Return the indices of the given character in the given string.
    Return an empty list if the character cannot be found.
    """
    return [i for i, c in enumerate(string) if c == char]


def substitute(command_list, dictionary):
    """
    Replace markup in the command_list which matches a key in the dictionary with the
    value of that key in the dictionary. Empty values leave the item unchanged.
    Markup needs to be safe to use in the final command as there is no guarantee that
    any dictionary will replace all markup in the command_list.
    arguments: command_list - a list of strings
               dictionary - a dictionary of keys which match some of the strings with values
                            to replace for the key in the string.
    """
    parsed = []
    for line in command_list:
        for key, value in dictionary.items():  # 2to3 false positive, works with python3
            if not key or not value:
                continue
            line = line.replace(key, value)
        parsed.append(line)
    return parsed
