# Copyright (C) 2014 Linaro Limited
#               2017 The Linux Foundation
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Jan-Simon Moeller <jsmoeller@linuxfoundation.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

# List just the subclasses supported for this base strategy
# imported by the parser to populate the list of subclasses.
from __future__ import annotations

import contextlib
import random
import socket
import subprocess  # nosec - internal use.
from contextvars import ContextVar

import netifaces
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from lava_common.constants import (
    VALID_DISPATCHER_IP_PROTOCOLS,
    XNBD_PORT_RANGE_MAX,
    XNBD_PORT_RANGE_MIN,
)
from lava_common.exceptions import InfrastructureError, LAVABug
from lava_dispatcher.utils.shell import which


def dispatcher_gateway():
    """
    Retrieves the IP address of the current default gateway.
    """
    gateways = netifaces.gateways()
    if "default" not in gateways:
        raise InfrastructureError("Unable to find default gateway")
    return gateways["default"][netifaces.AF_INET][0]


def dispatcher_ip(dispatcher_config, protocol=None):
    """
    Retrieves the IP address of the interface associated
    with the current default gateway.
    :param protocol: 'http', 'tftp' or 'nfs'
    """
    if protocol:
        if protocol not in VALID_DISPATCHER_IP_PROTOCOLS:
            raise LAVABug(
                "protocol should be one of %s" % VALID_DISPATCHER_IP_PROTOCOLS
            )
        with contextlib.suppress(KeyError, TypeError):
            return dispatcher_config["dispatcher_%s_ip" % protocol]
    with contextlib.suppress(KeyError, TypeError):
        return dispatcher_config["dispatcher_ip"]
    gateways = netifaces.gateways()
    if "default" not in gateways:
        raise InfrastructureError("Unable to find dispatcher 'default' gateway")
    iface = gateways["default"][netifaces.AF_INET][1]
    iface_addr = None

    try:
        addr = netifaces.ifaddresses(iface)
        iface_addr = addr[netifaces.AF_INET][0]["addr"]
    except KeyError:
        # TODO: This only handles first alias interface can be extended
        # to review all alias interfaces.
        addr = netifaces.ifaddresses(iface + ":0")
        iface_addr = addr[netifaces.AF_INET][0]["addr"]
    return iface_addr


def rpcinfo_nfs(server: str, version: int = 3) -> str | None:
    """
    Calls rpcinfo nfs on the specified server.
    Only stderr matters
    :param server: the NFS server to check
    :return: None if success, message if fail
    """
    rpcinfo_path = which("rpcinfo")

    rpcinfo_result = subprocess.run(
        (rpcinfo_path, "-t", server, "nfs", str(version)),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
    )
    if rpcinfo_result.returncode == 0:
        # Success
        return None

    return f"rpcinfo: {server} {rpcinfo_result.stderr}"


def get_free_port(dispatcher_config):
    """
    Finds the next free port to use
    :param dispatcher_config: the dispatcher config to search for nbd_server_port
    :return: port number
    """
    port = None
    with contextlib.suppress(KeyError, TypeError):
        dcport = dispatcher_config["nbd_server_port"]
        if "auto" in dcport:
            pass
        elif dcport.isdigit():
            return dcport
    # use random
    rng = random.Random()
    for _ in range(10):
        randport = int(rng.randrange(XNBD_PORT_RANGE_MIN, XNBD_PORT_RANGE_MAX))
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("", randport))
            s.listen(1)
            port = s.getsockname()[1]
        except OSError:
            s.close()
            continue
        s.close()
        if port is not None:
            return port
    # fallthrough single default nbd port as per services file
    return 10809


requests_session = ContextVar("requests_session")


def requests_retry():
    with contextlib.suppress(LookupError):
        return requests_session.get()

    session = requests.Session()
    # Retry 15 times over a period a bit longer than 10 minutes.
    retries = 15
    backoff_factor = 0.1
    status_forcelist = [
        # See https://en.wikipedia.org/wiki/List_of_HTTP_status_codes
        408,  # Request Timeout
        413,  # Payload Too Large
        425,  # Too Early
        429,  # Too Many Requests
        500,  # Internal Server Error
        502,  # Bad Gateway
        503,  # Service Unavailable
        504,  # Gateway Timeout
        507,  # Insufficient Storage
        # Unofficial codes
        420,  # Enhance Your Calm
        430,  # Request Header Fields Too Large
        509,  # Bandwidth Limit Exceeded
        529,  # Site is overloaded
        598,  # (Informal convention) Network read timeout error
    ]
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        status=retries,
        status_forcelist=status_forcelist,
        backoff_factor=backoff_factor,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    requests_session.set(session)
    return session
