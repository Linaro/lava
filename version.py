#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  version.py
#
#  Copyright 2014 Neil Williams <codehelp@debian.org>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import re
import subprocess  # nosec - internal
import os
import sys


# pylint: disable=superfluous-parens,too-many-locals


def version_tag():
    """
    Parses the git status to determine if this is a git tag
    or a developer commit and builds a version string combining
    the two. If there is no git directory, relies on this being
    a directory created from the tarball created by setup.py when
    it uses this script and retrieves the original version string
    from that.
    :return: a version string based on the tag and short hash
    """
    args = ["git", "describe"]
    if len(sys.argv) == 2:
        if sys.argv[1] != "sdist":
            args.append(sys.argv[1])
    if os.path.exists("./.git"):
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
    if os.path.exists("debian/changelog"):
        return (
            subprocess.check_output(  # nosec - internal
                ("dpkg-parsechangelog", "--show-field", "Version")
            )
            .strip()
            .decode("utf-8")
            .split("-")[0]
        )


def main():
    print(version_tag())
    return 0


if __name__ == "__main__":
    sys.exit(main())
