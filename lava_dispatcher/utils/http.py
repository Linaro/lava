# Copyright (C) 2024 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

if TYPE_CHECKING:
    import urllib3


requests_session: ContextVar[requests.Session] = ContextVar("requests_session")


class HTTPAdapterEnforceLength(HTTPAdapter):
    def build_response(
        self,
        req: requests.PreparedRequest,
        resp: urllib3.BaseHTTPResponse,
    ) -> requests.Response:
        resp.enforce_content_length = True
        return super().build_response(req, resp)


def create_new_requests_session() -> requests.Session:
    session = requests.Session()
    # Retry 15 times over a period a bit longer than 10 minutes.
    retries = 15
    backoff_factor = 0.1
    status_forcelist = (
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
    )
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        status=retries,
        status_forcelist=status_forcelist,
        backoff_factor=backoff_factor,
    )
    adapter = HTTPAdapterEnforceLength(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def requests_retry() -> requests.Session:
    try:
        return requests_session.get()
    except LookupError:
        new_session = create_new_requests_session()
        requests_session.set(new_session)
        return new_session
