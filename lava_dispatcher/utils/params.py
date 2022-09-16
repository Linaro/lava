# Copyright (C) 2022 Collabora
#
# Author: Ed Smith <ed.smith@collabora.com>
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
# along with this program; if not, see <http://www.gnu.org/licenses>.
import enum


class State(enum.Enum):
    """An internal enum to capture the state of the parser in
    substitute_parameters
    """

    INITIAL = 1
    SAW_DOLLAR = 2
    BRACED_VARIABLE = 3
    VARIABLE = 4


def substitute_parameters(value, get_param):
    """Replace any marked parameters in `value` by calling `get_param`
    for each parameter that's found.

    Parameters can be identified either as `$param` or
    `${param}`. Parameter names must begin with a letter or an
    underscore, and then must contain only letters, numbers and
    underscores.

    The priority in this routine is avoiding regressions caused by
    adding parameter interpolation to an existing codebase. For this
    reason:
    - All invalid constructs, like "${FOO" are left unchanged.
    - All missing parameters, like "${NO_SUCH_PARAM}" are left
      unchanged.
    """
    res = ""
    mode = State.INITIAL
    escaped = False
    param = ""

    for ch in value:
        if mode == State.INITIAL:
            if ch == "$":
                mode = State.SAW_DOLLAR
            elif ch == "\\":
                escaped = True
            else:
                escaped = False
                res += ch

        elif mode == State.SAW_DOLLAR:
            if ch == "{":
                mode = State.BRACED_VARIABLE
            elif ch.isalpha() or ch == "_":
                mode = State.VARIABLE
                param += ch
            else:
                res += ("\\" if escaped else "") + "$" + param
                escaped = False
                param = ""
                if ch == "$":
                    mode = State.SAW_DOLLAR
                else:
                    mode = State.INITIAL
                    if ch == "\\":
                        escaped = True
                    else:
                        escaped = False
                        res += ch

        elif mode == State.VARIABLE:
            if ch.isalnum() or ch == "_":
                param += ch
            else:
                replacement = get_param(param)
                if replacement is None:
                    if escaped:
                        res += "\\"
                    res += "$" + param
                elif escaped:
                    res += "$" + param
                else:
                    res += replacement
                param = ""
                escaped = False

                if ch == "$":
                    mode = State.SAW_DOLLAR
                else:
                    mode = State.INITIAL
                    if ch == "\\":
                        escaped = True
                    else:
                        res += ch

        elif mode == State.BRACED_VARIABLE:
            if len(param) == 0 and (ch.isalpha() or ch == "_"):
                param += ch
            elif len(param) > 0 and (ch.isalnum() or ch == "_"):
                param += ch
            elif ch == "}":
                replacement = get_param(param)
                if replacement is None:
                    if escaped:
                        res += "\\"
                    res += "${" + param + "}"
                elif escaped:
                    res += "${" + param + "}"
                else:
                    res += replacement
                param = ""
                escaped = False
                mode = State.INITIAL
            else:
                if escaped:
                    res += "\\"
                res += "${" + param
                param = ""
                escaped = False
                if ch == "$":
                    mode = State.SAW_DOLLAR
                else:
                    mode = State.INITIAL
                    if ch == "\\":
                        escaped = True
                    else:
                        res += ch
                    res += ch

    if mode == State.VARIABLE:
        replacement = get_param(param)
        if replacement is None:
            if escaped:
                res += "\\"
            res += "$" + param
        elif escaped:
            res += "$" + param
        else:
            res += replacement

    elif mode == State.BRACED_VARIABLE:
        if escaped:
            res += "\\"
        res += "${" + param
    elif mode == State.SAW_DOLLAR:
        if escaped:
            res += "\\"
        res += "$"
    elif escaped:
        res += "\\"

    return res
