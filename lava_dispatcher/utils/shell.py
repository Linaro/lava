# Copyright (C) 2014 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
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
from stat import S_IXUSR
from lava_dispatcher.action import InfrastructureError


def _which_check(path, match):
    """
    Simple replacement for the `which` command found on
    Debian based systems. Allows ordinary users to query
    the PATH used at runtime.
    """
    paths = os.environ['PATH'].split(':')
    if os.getuid() != 0:
        # avoid sudo - it may ask for a password on developer systems.
        paths.extend(['/usr/local/sbin', '/usr/sbin', '/sbin'])
    for dirname in paths:
        candidate = os.path.join(dirname, path)
        if match(candidate):
            return candidate
    return None


def which(path, match=os.path.isfile):
    ret = _which_check(path, match)
    if ret:
        return ret
    raise InfrastructureError("Cannot find command '%s' in $PATH" % path)


def infrastructure_error(path):
    """
    Extends which into a check which sets default messages for Action validation,
    without needing to raise an Exception (which is slow).
    Use for quick checks on whether essential tools are installed and usable.
    """
    exefile = _which_check(path, match=os.path.isfile)
    if not exefile:
        return "Cannot find command '%s' in $PATH" % path
    # is the infrastructure call safe to make?
    if exefile and os.stat(exefile).st_mode & S_IXUSR != S_IXUSR:
        return "%s is not executable" % exefile
    return None


def infrastructure_error_multi_paths(path_list):
    """
    Similar to infrastructure_error, but accepts a list of paths.
    """
    for path in path_list:
        if infrastructure_error(path):
            return infrastructure_error(path)
