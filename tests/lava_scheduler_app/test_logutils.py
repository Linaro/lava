# Copyright (C) 2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import lzma
import unittest

import pytest
from django.conf import settings

from lava_common.yaml import yaml_safe_dump, yaml_safe_load
from lava_scheduler_app.logutils import LogsElasticsearch, LogsFilesystem, LogsMongo


def check_pymongo():
    try:
        import pymongo

        return False
    except ImportError:
        return True


@pytest.fixture
def logs_elasticsearch(mocker):
    mocker.patch("requests.put")
    return LogsElasticsearch()


@pytest.fixture
def logs_filesystem():
    return LogsFilesystem()


def test_read_logs_uncompressed(mocker, tmp_path, logs_filesystem):
    job = mocker.Mock()
    job.output_dir = tmp_path
    (tmp_path / "output.yaml").write_text(
        "hello\nworld\nhow\nare\nyou", encoding="utf-8"
    )
    assert logs_filesystem.read(job) == "hello\nworld\nhow\nare\nyou"  # nosec
    assert not (tmp_path / "output.idx").exists()  # nosec

    # If output.yaml exists, read_logs should use it
    with lzma.open(str(tmp_path / "output.yaml.xz"), "wb") as f_logs:
        f_logs.write(b"compressed")
    assert logs_filesystem.read(job) == "hello\nworld\nhow\nare\nyou"  # nosec
    assert not (tmp_path / "output.idx").exists()  # nosec

    # Test the index
    assert logs_filesystem.read(job, start=1) == "world\nhow\nare\nyou"  # nosec
    assert (tmp_path / "output.idx").exists()  # nosec
    assert logs_filesystem.read(job, start=1, end=2) == "world\n"  # nosec
    assert logs_filesystem.read(job, start=1, end=3) == "world\nhow\n"  # nosec
    assert logs_filesystem.read(job, start=4, end=5) == "you"  # nosec
    assert logs_filesystem.read(job, start=5, end=50) == ""  # nosec


def test_read_logs_compressed(mocker, tmp_path, logs_filesystem):
    job = mocker.Mock()
    job.output_dir = tmp_path
    with lzma.open(str(tmp_path / "output.yaml.xz"), "wb") as f_logs:
        f_logs.write(b"compressed\nor\nnot")
    assert logs_filesystem.read(job) == "compressed\nor\nnot"  # nosec
    assert not (tmp_path / "output.idx").exists()  # nosec

    # Use the index
    assert logs_filesystem.read(job, start=1) == "or\nnot"  # nosec
    assert (tmp_path / "output.idx").exists()  # nosec
    assert logs_filesystem.read(job, start=1, end=2) == "or\n"  # nosec
    assert logs_filesystem.read(job, start=1, end=20) == "or\nnot"  # nosec
    assert logs_filesystem.read(job, start=2, end=2) == ""  # nosec
    assert logs_filesystem.read(job, start=1, end=0) == ""  # nosec


def test_size_logs(mocker, tmp_path, logs_filesystem):
    job = mocker.Mock()
    job.output_dir = tmp_path
    with lzma.open(str(tmp_path / "output.yaml.xz"), "wb") as f_logs:
        f_logs.write(b"hello world\nhow are you?\n")
    # "output.yaml.size" is missing
    assert logs_filesystem.size(job) is None  # nosec
    (tmp_path / "output.yaml.size").write_text("25", encoding="utf-8")
    assert logs_filesystem.size(job) == 25  # nosec

    with open(str(tmp_path / "output.yaml"), "wb") as f_logs:
        f_logs.write(b"hello world!\n")
    assert logs_filesystem.size(job) == 13  # nosec


def test_write_logs(mocker, tmp_path, logs_filesystem):
    job = mocker.Mock()
    job.output_dir = tmp_path
    with open(str(tmp_path / "output.yaml"), "wb") as f_logs:
        with open(str(tmp_path / "output.idx"), "wb") as f_idx:
            logs_filesystem.write(job, b"hello world\n", f_logs, f_idx)
            logs_filesystem.write(job, b"how are you?\n", f_logs, f_idx)
    assert logs_filesystem.read(job) == "hello world\nhow are you?\n"  # nosec
    assert logs_filesystem.size(job) == 25  # nosec
    with open(str(tmp_path / "output.idx"), "rb") as f_idx:
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
    result = yaml_safe_load(logs_mongo.read(job))

    assert len(result) == 2  # nosec
    assert result == find_ret_val  # nosec
    # size of find_ret_val in bytes
    assert logs_mongo.size(job) == 137  # nosec

    assert logs_mongo.read(job) == yaml_safe_dump(find_ret_val)


def test_elasticsearch_logs(mocker, logs_elasticsearch):
    job = mocker.Mock()
    job.id = 1

    post = mocker.MagicMock()
    get = mocker.MagicMock()
    get_ret_val = mocker.Mock()

    # Test with empty object first.
    get_ret_val.text = "{}"
    get.return_value = get_ret_val
    mocker.patch("requests.get", get)
    result = logs_elasticsearch.read(job)
    assert result == ""

    # Normal test.
    get_ret_val.text = '{"hits":{"hits":[{"_source":{"dt": 1585165476209, "lvl": "info", "msg": "first message"}}, {"_source":{"dt": 1585165476210, "lvl": "info", "msg": "second message"}}]}}'
    get.return_value = get_ret_val

    mocker.patch("requests.get", get)
    mocker.patch("requests.post", post)

    line = '- {"dt": "2020-03-25T19:44:36.209", "lvl": "info", "msg": "lava-dispatcher, installed at version: 2020.02"}'
    logs_elasticsearch.write(job, line)
    post.assert_called_with(
        "%s%s/_doc/" % (settings.ELASTICSEARCH_URI, settings.ELASTICSEARCH_INDEX),
        data='{"dt": 1585165476209, "lvl": "info", "msg": "lava-dispatcher, installed at version: 2020.02", "job_id": 1}',
        headers={"Content-type": "application/json"},
    )  # nosec
    result = yaml_safe_load(logs_elasticsearch.read(job))

    assert len(result) == 2  # nosec
    assert result == [
        {"dt": "2020-03-25T19:44:36.209000", "lvl": "info", "msg": "first message"},
        {"dt": "2020-03-25T19:44:36.210000", "lvl": "info", "msg": "second message"},
    ]  # nosec
    # size of get_ret_val in bytes
    assert logs_elasticsearch.size(job) == 137  # nosec

    assert logs_elasticsearch.read(job) == yaml_safe_dump(
        [
            {
                "dt": "2020-03-25T19:44:36.209000",
                "lvl": "info",
                "msg": "first message",
            },
            {
                "dt": "2020-03-25T19:44:36.210000",
                "lvl": "info",
                "msg": "second message",
            },
        ]
    )
