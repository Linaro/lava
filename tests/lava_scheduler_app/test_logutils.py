# -*- coding: utf-8 -*-
# Copyright (C) 2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA.  If not, see <http://www.gnu.org/licenses/>.

import lzma
import pytest
import unittest

from lava_common.compat import yaml_dump, yaml_load
from lava_scheduler_app.logutils import LogsFilesystem, LogsMongo


def check_pymongo():
    try:
        import pymongo

        return False
    except ImportError:
        return True


@pytest.fixture
def logs_filesystem():
    return LogsFilesystem()


def test_read_logs_uncompressed(mocker, tmpdir, logs_filesystem):
    job = mocker.Mock()
    job.output_dir = tmpdir
    (tmpdir / "output.yaml").write_text("hello\nworld\nhow\nare\nyou", encoding="utf-8")
    assert logs_filesystem.read(job) == "hello\nworld\nhow\nare\nyou"  # nosec
    assert not (tmpdir / "output.idx").exists()  # nosec

    # If output.yaml exists, read_logs should use it
    with lzma.open(str(tmpdir / "output.yaml.xz"), "wb") as f_logs:
        f_logs.write("compressed".encode("utf-8"))
    assert logs_filesystem.read(job) == "hello\nworld\nhow\nare\nyou"  # nosec
    assert not (tmpdir / "output.idx").exists()  # nosec

    # Test the index
    assert logs_filesystem.read(job, start=1) == "world\nhow\nare\nyou"  # nosec
    assert (tmpdir / "output.idx").exists()  # nosec
    assert logs_filesystem.read(job, start=1, end=2) == "world\n"  # nosec
    assert logs_filesystem.read(job, start=1, end=3) == "world\nhow\n"  # nosec
    assert logs_filesystem.read(job, start=4, end=5) == "you"  # nosec
    assert logs_filesystem.read(job, start=5, end=50) == ""  # nosec


def test_read_logs_compressed(mocker, tmpdir, logs_filesystem):
    job = mocker.Mock()
    job.output_dir = tmpdir
    with lzma.open(str(tmpdir / "output.yaml.xz"), "wb") as f_logs:
        f_logs.write("compressed\nor\nnot".encode("utf-8"))
    assert logs_filesystem.read(job) == "compressed\nor\nnot"  # nosec
    assert not (tmpdir / "output.idx").exists()  # nosec

    # Use the index
    assert logs_filesystem.read(job, start=1) == "or\nnot"  # nosec
    assert (tmpdir / "output.idx").exists()  # nosec
    assert logs_filesystem.read(job, start=1, end=2) == "or\n"  # nosec
    assert logs_filesystem.read(job, start=1, end=20) == "or\nnot"  # nosec
    assert logs_filesystem.read(job, start=2, end=2) == ""  # nosec
    assert logs_filesystem.read(job, start=1, end=0) == ""  # nosec


def test_size_logs(mocker, tmpdir, logs_filesystem):
    job = mocker.Mock()
    job.output_dir = tmpdir
    with lzma.open(str(tmpdir / "output.yaml.xz"), "wb") as f_logs:
        f_logs.write("hello world\nhow are you?\n".encode("utf-8"))
    # "output.yaml.size" is missing
    assert logs_filesystem.size(job) is None  # nosec
    (tmpdir / "output.yaml.size").write_text("25", encoding="utf-8")
    assert logs_filesystem.size(job) == 25  # nosec

    with open(str(tmpdir / "output.yaml"), "wb") as f_logs:
        f_logs.write("hello world!\n".encode("utf-8"))
    assert logs_filesystem.size(job) == 13  # nosec


def test_write_logs(mocker, tmpdir, logs_filesystem):
    job = mocker.Mock()
    job.output_dir = tmpdir
    with open(str(tmpdir / "output.yaml"), "wb") as f_logs:
        with open(str(tmpdir / "output.idx"), "wb") as f_idx:
            logs_filesystem.write(job, "hello world\n".encode("utf-8"), f_logs, f_idx)
            logs_filesystem.write(job, "how are you?\n".encode("utf-8"), f_logs, f_idx)
    assert logs_filesystem.read(job) == "hello world\nhow are you?\n"  # nosec
    assert logs_filesystem.size(job) == 25  # nosec
    with open(str(tmpdir / "output.idx"), "rb") as f_idx:
        assert f_idx.read(8) == b"\x00\x00\x00\x00\x00\x00\x00\x00"  # nosec
        assert f_idx.read(8) == b"\x0c\x00\x00\x00\x00\x00\x00\x00"  # nosec


@unittest.skipIf(check_pymongo(), "openocd not installed")
def test_mongo_logs(mocker):
    mocker.patch("pymongo.database.Database.command")
    mocker.patch("pymongo.collection.Collection.create_index")
    logs_mongo = LogsMongo()

    job = mocker.Mock()
    job.id = 1

    insert_one = mocker.MagicMock()
    find = mocker.MagicMock()
    find_ret_val = [
        {"dt": "2020-03-25T19:44:36.209548", "lvl": "info", "msg": "first message"},
        {"dt": "2020-03-26T19:44:36.209548", "lvl": "info", "msg": "second message"},
    ]
    find.return_value = find_ret_val

    mocker.patch("pymongo.collection.Collection.find", find)
    mocker.patch("pymongo.collection.Collection.insert_one", insert_one)

    logs_mongo.write(
        job,
        '- {"dt": "2020-03-25T19:44:36.209548", "lvl": "info", "msg": "lava-dispatcher, installed at version: 2020.02"}',
    )
    insert_one.assert_called_with(
        {
            "job_id": 1,
            "dt": "2020-03-25T19:44:36.209548",
            "lvl": "info",
            "msg": "lava-dispatcher, installed at version: 2020.02",
        }
    )  # nosec
    result = yaml_load(logs_mongo.read(job))

    assert len(result) == 2  # nosec
    assert result == find_ret_val  # nosec
    # size of find_ret_val in bytes
    assert logs_mongo.size(job) == 137  # nosec

    assert logs_mongo.open(job).read() == yaml_dump(find_ret_val).encode("utf-8")
