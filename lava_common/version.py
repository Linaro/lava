#!/usr/bin/env python3
#
# Copyright (C) 2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import argparse
import contextlib
import pathlib
import re
import subprocess


def version(ref=None):
    root = pathlib.Path(__file__) / ".." / ".."
    root = root.resolve()
    with contextlib.suppress(FileNotFoundError):
        if (root / ".git").exists():
            args = ["git", "-C", str(root), "describe", "--match=[0-9]*"]
            if ref is not None:
                args.append(ref)
            pattern = re.compile(r"(?P<tag>.+)-(?P<commits>\d+)-g(?P<hash>[abcdef\d]+)")
            describe = (
                subprocess.check_output(args)
                .strip()
                .decode("utf-8")  # nosec - internal
            )
            m = pattern.match(describe)
            if m is None:
                return describe
            else:
                d = m.groupdict()
                return f"{d['tag']}.dev{int(d['commits']):04}"
    return (root / "lava_common" / "VERSION").read_text(encoding="utf-8").rstrip()


__version__ = version()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ref", nargs="?", default=None, help="reference")

    options = parser.parse_args()
    print(version(options.ref))
