#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses>.

import json
import re
import os
import sys
import string
import subprocess  # nosec - internal

FILENAME = "gl-code-quality-report.json"


def main(args):
    data = []
    p = subprocess.Popen(  # nosec - internal
        ["/usr/bin/radon", "cc", "--min", "D", "--codeclimate", "."],
        stdout=subprocess.PIPE,
    )
    with p.stdout:
        for line in iter(p.stdout.readline, b""):
            data.append(line.decode("utf-8", errors="replace"))
    p.wait()  # wait for the subprocess to exit
    data_str = data[0]
    data_str = re.sub(f"[^{re.escape(string.printable)}]", "", data_str)
    with open(FILENAME, "w") as radon:
        radon.write("[\n%s\n]" % data_str.replace("}{", "},\n{"))

    ret = []
    with open(FILENAME, "r") as f_in:
        data = json.load(f_in)
    for line in data:
        ret.append(
            "%s [%s, %s]: %s"
            % (
                line["location"]["path"],
                line["location"]["lines"]["begin"],
                line["location"]["lines"]["end"],
                line["description"],
            )
        )
    print("\n".join(sorted(ret)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
