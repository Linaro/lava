# Copyright (C) 2026 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later

import json

import pytest

from lava_dispatcher_host.client import Client


@pytest.mark.parametrize(
    "response, expected",
    [
        (b'{"result": "OK"}\n', {"result": "OK"}),
        # a FAILED reply longer than one recv buffer must not be
        # truncated
        (
            json.dumps({"result": "FAILED", "message": "X" * 2000}).encode() + b"\n",
            {"result": "FAILED", "message": "X" * 2000},
        ),
        # the server closes the connection without a reply when the
        # peer is not root
        (b"", {"result": "NO_RESPONSE"}),
    ],
)
def test_send_request_returns_parsed_response(mocker, response, expected):
    sock = mocker.patch("lava_dispatcher_host.client.socket.socket")()
    # deliver in sub-buffer chunks so a single-recv implementation fails
    sock.__enter__.return_value.recv.side_effect = [
        response[:1000],
        response[1000:],
        b"",
    ]
    assert Client("/dev/null").send_request({"device": "foo"}) == expected
