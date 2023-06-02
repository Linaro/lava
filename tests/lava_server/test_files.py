# Copyright (C) 2020-present Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pytest
from jinja2 import FileSystemLoader

from lava_server.files import File


def test_file_device(mocker, tmp_path):
    mocker.patch(
        "lava_server.files.File.KINDS",
        {
            "device": ([str(tmp_path / "devices")], "{name}.jinja2"),
            "device-type": ([str(tmp_path / "device-types")], "{name}.jinja2"),
        },
    )
    assert File("device", "hello").exists() is False
    # Create the file
    File("device", "hello").write("hello world!")
    assert File("device", "hello").exists() is True
    assert File("device", "hello").read() == "hello world!"

    ret = File("device").list("*.jinja2")
    assert len(ret) == 1
    assert ret[0] == "hello.jinja2"

    ret = File("device").list("*.yaml")
    assert len(ret) == 0

    assert isinstance(File("device").loader(), FileSystemLoader) is True
    assert File("device").loader().searchpath == [
        str(tmp_path / "devices"),
        str(tmp_path / "device-types"),
    ]


def test_file_device_type(mocker, tmp_path):
    mocker.patch(
        "lava_server.files.File.KINDS",
        {"device-type": ([str(tmp_path / "0"), str(tmp_path / "1")], "{name}.jinja2")},
    )
    assert File("device-type", "hello").exists() is False

    # Test fallback
    (tmp_path / "1").mkdir()
    (tmp_path / "1" / "hello.jinja2").write_text("base", encoding="utf-8")
    assert File("device-type", "hello").read() == "base"

    # Create the file
    File("device-type", "hello").write("new version")
    assert File("device-type", "hello").exists() is True
    assert File("device-type", "hello").read() == "new version"
    assert File("device-type", "hello").is_first() is True

    ret = File("device-type").list("*.yaml")
    assert len(ret) == 0

    ret = File("device-type").list("*.jinja2")
    assert len(ret) == 1
    assert ret[0] == "hello.jinja2"

    assert File("device-type").loader().searchpath == [
        str(tmp_path / "0"),
        str(tmp_path / "1"),
    ]

    # Delete the file
    File("device-type", "hello").write("")
    assert File("device-type", "hello").exists() is True
    assert File("device-type", "hello").read() == "base"
    assert File("device-type", "hello").is_first() is False


def test_file_env(mocker, tmp_path):
    mocker.patch(
        "lava_server.files.File.KINDS",
        {"env": [str(tmp_path / "{name}/env.yaml"), str(tmp_path / "env.yaml")]},
    )
    assert File("env", "worker01").exists() is False

    # Test fallback
    (tmp_path / "worker01").mkdir()
    (tmp_path / "worker01" / "env.yaml").write_text("base", encoding="utf-8")
    assert File("env", "worker01").read() == "base"

    # Create the file
    File("env", "worker01").write("new version")
    assert File("env", "worker01").exists() is True
    assert File("env", "worker01").read() == "new version"


def test_file_errors(mocker, tmp_path):
    mocker.patch(
        "lava_server.files.File.KINDS",
        {
            "health-check": (
                [str(tmp_path / "0"), str(tmp_path / "1")],
                "{name}.jinja2",
            ),
            "env": [str(tmp_path / "env")],
        },
    )

    with pytest.raises(NotImplementedError):
        File("health-checks")

    with pytest.raises(NotImplementedError):
        File("health-check").loader()

    with pytest.raises(NotImplementedError):
        File("env").list("*.yaml")

    with pytest.raises(FileNotFoundError):
        File("health-check", "docker").read()
    assert File("health-check", "docker").read(raising=False) == ""
