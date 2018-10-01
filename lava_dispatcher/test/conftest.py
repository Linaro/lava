# -*- coding: utf-8 -*-
# Copyright (C) 2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import pytest
import requests


@pytest.fixture(autouse=True)
def no_requests(monkeypatch, request):
    def get(url, allow_redirects, stream):
        assert allow_redirects is True  # nosec - unit test support
        assert stream is True  # nosec - unit test support
        res = requests.Response()
        res.status_code = requests.codes.OK
        res.close = lambda: None
        return res

    # List of tests that should have access to the network
    # When pytest is mandatory, we can use pytest marks
    # See https://stackoverflow.com/a/38763328
    skip_tests = ["test_download_decompression", "TestChecksum", "test_xz_nfs"]
    if set(skip_tests) & set(request.keywords.keys()):
        return
    monkeypatch.setattr(requests, "get", get)
