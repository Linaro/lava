# Copyright (C) 2016 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
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

import os
import re


def add_late_command(preseedfile, extra_command):
    added = False
    append_line = " ; " + extra_command + "\n"
    with open(preseedfile, "r") as pf:
        lines = pf.readlines()
        pf.close()
    endstring = '\\\n'
    while endsin(lines, endstring):
        for linenum, data in enumerate(lines):
            if endsin(data, endstring):
                lines[linenum] = lines[linenum].replace(endstring, '') + lines[linenum + 1]
                del lines[linenum + 1]
    for linenum, data in enumerate(lines):
        if re.match("d-i preseed/late_command string(.*)", data):
            # late_command already exists, append to it
            lines[linenum] = lines[linenum].rstrip() + append_line
            added = True
    if not added:
        lines.append("d-i preseed/late_command string " + append_line)

    with open(preseedfile, "w") as pf:
        for line in lines:
            pf.write(line)
        pf.close()


def endsin(lines, endstring):
    match = False
    if type(lines) is list:
        for line in lines:
            if line.endswith(endstring):
                match = True
    elif type(lines) is str:
        if lines.endswith(endstring):
            match = True
    return match
