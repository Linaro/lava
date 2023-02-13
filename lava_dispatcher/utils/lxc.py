# Copyright (C) 2018 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

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
