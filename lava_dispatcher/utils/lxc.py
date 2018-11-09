# Copyright (C) 2018 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
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

from lava_common.constants import LXC_PROTOCOL


def is_lxc_requested(job):
    """Checks if LXC protocol is requested.

    Returns the LXC_NAME of the container if the job requests LXC, else False.
    """
    if job:
        protocol = [p for p in job.protocols if p.name == LXC_PROTOCOL]
        if protocol:
            return protocol[0].lxc_name
    return False


def lxc_cmd_prefix(job):
    name = is_lxc_requested(job)
    if not name:
        return []
    return ["lxc-attach", "-n", name, "--"]
