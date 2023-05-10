#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import json
import os
import re
import string
import subprocess  # nosec - internal
import sys

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
