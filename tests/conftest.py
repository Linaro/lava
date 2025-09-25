# Copyright (C) 2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os

import pytest
import requests

import lava_dispatcher.job
import lava_dispatcher.utils.filesystem

os.environ["LANGUAGE"] = "C.UTF-8"


# @pytest.fixture
# def job_config(tmp_path):
#     return {"dispatcher_download_path": tmp_path}


@pytest.fixture(autouse=True)
def tempdir(monkeypatch, tmp_path):
    monkeypatch.setattr(
        lava_dispatcher.utils.filesystem,
        "dispatcher_download_dir",
        lambda _: str(tmp_path),
    )
    monkeypatch.setattr(
        lava_dispatcher.utils.filesystem, "tftpd_dir", lambda: str(tmp_path)
    )


class LavaTestOverwriteInConftest(NotImplementedError): ...


@pytest.fixture(autouse=True)
def no_network(mocker, request):
    def get(url, allow_redirects, stream, headers, timeout):
        assert allow_redirects is True  # nosec - unit test support
        assert stream is True  # nosec - unit test support
        res = requests.Response()
        res.status_code = requests.codes.OK
        res.close = lambda: None
        res.raw = LavaTestOverwriteInConftest()
        return res

    def head(url, allow_redirects, headers, timeout):
        assert allow_redirects is True  # nosec - unit test support
        print(url)
        res = requests.Response()
        res.status_code = requests.codes.OK
        res.raw = LavaTestOverwriteInConftest()
        res.close = lambda: None
        return res

    # List of tests that should have access to the network
    # When pytest is mandatory, we can use pytest marks
    # See https://stackoverflow.com/a/38763328
    skip_tests = {
        "test_bad_download_decompression",
        "test_download_decompression",
        "test_invalid_multinode",
    }
    if not skip_tests & set(request.keywords.keys()):
        mocker.patch("requests.head", head)
        mocker.patch("requests.get", get)
        mocker.patch(
            "lava_dispatcher.actions.deploy.download.requests_retry",
            lambda retries=15: requests,
        )

    # Fake lava_dispatcher.utils.network to always return the same results
    def gateways():
        return "eth0"

    def ifaddresses(iface):
        assert iface == "eth0"  # nosec - unit test support
        return "192.168.0.2"

    mocker.patch("lava_dispatcher.utils.network.get_default_iface", gateways)
    mocker.patch("lava_dispatcher.utils.network.get_iface_addr", ifaddresses)
