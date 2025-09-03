# Copyright (C) 2014-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import os
from itertools import product
from stat import S_IXUSR
from typing import TYPE_CHECKING

from lava_common.exceptions import InfrastructureError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


def _which_check(
    names_to_find: Iterable[str], match: Callable[[str], object]
) -> str | None:
    """
    Simple replacement for the `which` command found on
    Debian based systems. Allows ordinary users to query
    the PATH used at runtime.
    """
    paths = os.environ["PATH"].split(":")
    if os.getuid() != 0:
        # avoid sudo - it may ask for a password on developer systems.
        paths.extend(["/usr/local/sbin", "/usr/sbin", "/sbin"])

    # Search in the order of file name first over the path.
    # For example:
    #   names_to_find=["pyocd", "pyocd-flashtool"]
    #   paths=["/usr/bin/local", "/usr/bin"]
    # Search order:
    #   1. /usr/bin/local/pyocd
    #   2. /usr/bin/pyocd
    #   3. /usr/bin/local/pyocd-flashtool
    #   4. /usr/bin/pyocd-flashtool
    for file_name, dirname in product(names_to_find, paths):
        candidate = os.path.join(dirname, file_name)
        if match(candidate):
            return os.path.realpath(candidate)
    return None


def which(
    path: str | Iterable[str], match: Callable[[str], object] = os.path.isfile
) -> str:
    if isinstance(path, str):
        path = (path,)

    exefile = _which_check(path, match)
    if not exefile:
        raise InfrastructureError("Cannot find command '%s' in $PATH" % path)

    if os.stat(exefile).st_mode & S_IXUSR != S_IXUSR:
        raise InfrastructureError("Cannot execute '%s' at '%s'" % (path, exefile))

    return exefile
