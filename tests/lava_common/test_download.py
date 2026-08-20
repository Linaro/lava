# Copyright (C) 2026 Qualcomm Technologies, Inc. and/or its subsidiaries.
#
# Author: Christopher Obbard <chris.obbard@oss.qualcomm.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import os
from pathlib import Path

from lava_common.constants import DISPATCHER_DOWNLOAD_DIR
from lava_common.download import dispatcher_download_dir, resolve_download_dir


def test_default():
    assert resolve_download_dir() == Path(DISPATCHER_DOWNLOAD_DIR)


def test_no_override():
    # None and the empty string both mean "nothing was configured"
    assert resolve_download_dir(None) == Path(DISPATCHER_DOWNLOAD_DIR)
    assert resolve_download_dir("") == Path(DISPATCHER_DOWNLOAD_DIR)


def test_absolute_path():
    assert resolve_download_dir("/srv/lava/downloads") == Path("/srv/lava/downloads")


def test_path_object():
    assert resolve_download_dir(Path("/srv/lava/downloads")) == Path(
        "/srv/lava/downloads"
    )


def test_relative_path(tmp_path, monkeypatch):
    # The directory is shared between processes which do not have the same
    # working directory, so a relative path is resolved by the process reading
    # the configuration.
    monkeypatch.chdir(tmp_path)
    assert resolve_download_dir("downloads") == Path(os.getcwd()) / "downloads"


# The dispatcher configuration comes straight from the configuration file, so
# anything can be found there, including nothing at all.


def test_config_configured():
    assert (
        dispatcher_download_dir({"dispatcher_download_dir": "/tmp/downloads"})
        == "/tmp/downloads"
    )


def test_config_configured_relative(tmp_path, monkeypatch):
    # Resolved against the working directory of the process reading the
    # configuration, which is not the one of every user of the directory.
    monkeypatch.chdir(tmp_path)
    assert dispatcher_download_dir({"dispatcher_download_dir": "downloads"}) == str(
        Path(os.getcwd()) / "downloads"
    )


def test_config_missing():
    assert dispatcher_download_dir(None) == DISPATCHER_DOWNLOAD_DIR


def test_config_empty():
    assert dispatcher_download_dir({}) == DISPATCHER_DOWNLOAD_DIR


def test_config_not_a_dict():
    assert dispatcher_download_dir(["not", "a", "dict"]) == DISPATCHER_DOWNLOAD_DIR


def test_config_empty_key():
    assert dispatcher_download_dir({"dispatcher_download_dir": None}) == (
        DISPATCHER_DOWNLOAD_DIR
    )
