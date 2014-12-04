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

from lava_dispatcher.pipeline.action import InfrastructureError


def which(path, match=os.path.isfile):
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
    raise InfrastructureError("Cannot find command '%s' in $PATH" % path)
