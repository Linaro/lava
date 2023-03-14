# Copyright (C) 2020 Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pytest

from lava_common.exceptions import LAVABug
from lava_dispatcher.utils.network import dispatcher_ip


def test_dispatcher_ip_missing():
    assert dispatcher_ip({}) == "192.168.0.2"


def test_dispatcher_ip():
    assert dispatcher_ip({"dispatcher_ip": "127.0.0.1"}) == "127.0.0.1"


def test_dispatcher_ip_invalid_protocol():
    with pytest.raises(LAVABug):
        dispatcher_ip({}, "bogus_protocol")


def test_dispatcher_ip_http():
    assert (
        dispatcher_ip(
            {"dispatcher_ip": "127.0.0.1", "dispatcher_http_ip": "192.168.1.2"}, "http"
        )
        == "192.168.1.2"
    )
    # Fall back to dispatcher_ip if dispatcher_http_ip is missing.
    assert dispatcher_ip({"dispatcher_ip": "127.0.0.1"}, "http") == "127.0.0.1"


def test_dispatcher_ip_http_port():
    assert (
        dispatcher_ip(
            {"dispatcher_ip": "127.0.0.1", "dispatcher_http_ip": "192.168.1.2:8080"},
            "http",
        )
        == "192.168.1.2:8080"
    )
    # Fall back to dispatcher_ip if dispatcher_http_ip is missing.
    assert dispatcher_ip({"dispatcher_ip": "127.0.0.1"}, "http") == "127.0.0.1"


def test_dispatcher_ip_tftp():
    assert (
        dispatcher_ip(
            {"dispatcher_ip": "127.0.0.1", "dispatcher_tftp_ip": "192.168.1.2"}, "tftp"
        )
        == "192.168.1.2"
    )
    # Fall back to dispatcher_ip if dispatcher_tftp_ip is missing.
    assert dispatcher_ip({"dispatcher_ip": "127.0.0.1"}, "tftp") == "127.0.0.1"


def test_dispatcher_ip_nfs():
    assert (
        dispatcher_ip(
            {"dispatcher_ip": "127.0.0.1", "dispatcher_nfs_ip": "192.168.1.2"}, "nfs"
        )
        == "192.168.1.2"
    )
    # Fall back to dispatcher_ip if dispatcher_nfs_ip is missing.
    assert dispatcher_ip({"dispatcher_ip": "127.0.0.1"}, "nfs") == "127.0.0.1"
