# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
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

# List just the subclasses supported for this base strategy
# imported by the parser to populate the list of subclasses.

import os
import netifaces
import subprocess
from lava_dispatcher.pipeline.action import InfrastructureError


# pylint: disable=no-member


def dispatcher_gateway():
    """
    Retrieves the IP address of the current default gateway.
    """
    gateways = netifaces.gateways()
    if 'default' not in gateways:
        raise InfrastructureError("Unable to find default gateway")
    return gateways['default'][netifaces.AF_INET][0]


def dispatcher_ip():
    """
    Retrieves the IP address of the interface associated
    with the current default gateway.
    """
    gateways = netifaces.gateways()
    if 'default' not in gateways:
        raise InfrastructureError("Unable to find default gateway")
    iface = gateways['default'][netifaces.AF_INET][1]
    addr = netifaces.ifaddresses(iface)
    return addr[netifaces.AF_INET][0]['addr']


def rpcinfo_nfs(server):
    """
    Calls rpcinfo nfs on the specified server.
    Only stderr matters
    :param server: the NFS server to check
    :return: None if success, message if fail
    """
    with open(os.devnull, 'w') as devnull:
        proc = subprocess.Popen(['/usr/sbin/rpcinfo', '-u', server, 'nfs'], stdout=devnull, stderr=subprocess.PIPE)
        msg = proc.communicate()
        if msg[1]:
            return "%s %s" % (server, msg[1])
    return None
