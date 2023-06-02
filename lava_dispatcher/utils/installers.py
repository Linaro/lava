# Copyright (C) 2016 Linaro Limited
#
# Author: Matthew Hart <matthew.hart@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import re


def add_to_kickstart(preseedfile, extra_command):
    with open(preseedfile, "a") as pf:
        pf.write("\n")
        pf.write("%post\n")
        pf.write("exec < /dev/console > /dev/console\n")
        pf.write(extra_command + "\n")
        pf.write("%end\n")
    pf.close()


def add_late_command(preseedfile, extra_command):
    added = False
    with open(preseedfile) as pf:
        lines = pf.readlines()
        pf.close()
    endstring = "\\\n"
    while endsin(lines, endstring):
        for linenum, data in enumerate(lines):
            if endsin(data, endstring):
                lines[linenum] = (
                    lines[linenum].replace(endstring, "") + lines[linenum + 1]
                )
                del lines[linenum + 1]
    for linenum, data in enumerate(lines):
        if re.match("d-i preseed/late_command string(.*)", data):
            # late_command already exists, append to it
            append_line = "; " + extra_command + "\n"
            lines[linenum] = lines[linenum].rstrip(" ;\n") + append_line
            added = True
    if not added:
        append_line = extra_command + "\n"
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
