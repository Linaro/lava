#!/usr/bin/env python3
#
# Copyright (C) 2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
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
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import argparse
import pathlib
import re
import subprocess


def version(ref=None):
    root = pathlib.Path(__file__) / ".." / ".."
    root = root.resolve()
    if (root / ".git").exists():
        args = ["git", "-C", str(root), "describe", "--match=[0-9]*"]
        if ref is not None:
            args.append(ref)
        pattern = re.compile(r"(?P<tag>.+)\.(?P<commits>\d+)\.g(?P<hash>[abcdef\d]+)")
        describe = (
            subprocess.check_output(args)  # nosec - internal
            .strip()
            .decode("utf-8")
            .replace("-", ".")
        )
        m = pattern.match(describe)
        if m is None:
            return describe
        else:
            d = m.groupdict()
            return "%s.%04d.g%s" % (d["tag"], int(d["commits"]), d["hash"])
    else:
        return (root / "lava_common" / "VERSION").read_text(encoding="utf-8").rstrip()


__version__ = version()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ref", nargs="?", default=None, help="reference")

    options = parser.parse_args()
    print(version(options.ref))
