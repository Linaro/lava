# Copyright (C) 2014-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
from stat import S_IXUSR

from lava_common.exceptions import InfrastructureError


def _which_check(path, match):
    """
    Simple replacement for the `which` command found on
    Debian based systems. Allows ordinary users to query
    the PATH used at runtime.
    """
    paths = os.environ["PATH"].split(":")
    if os.getuid() != 0:
        # avoid sudo - it may ask for a password on developer systems.
        paths.extend(["/usr/local/sbin", "/usr/sbin", "/sbin"])
    for dirname in paths:
        candidate = os.path.join(dirname, path)
        if match(candidate):
            return os.path.realpath(candidate)
    return None


def which(path, match=os.path.isfile):
    exefile = _which_check(path, match)
    if not exefile:
        raise InfrastructureError("Cannot find command '%s' in $PATH" % path)

    if os.stat(exefile).st_mode & S_IXUSR != S_IXUSR:
        raise InfrastructureError("Cannot execute '%s' at '%s'" % (path, exefile))

    return exefile
