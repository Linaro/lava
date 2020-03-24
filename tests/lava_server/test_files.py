# -*- coding: utf-8 -*-
# Copyright (C) 2020-present Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
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

import jinja2
import pytest

from lava_server.files import File


def test_file_device(mocker, tmpdir):
    mocker.patch(
        "lava_server.files.File.KINDS",
        {
            "device": ([str(tmpdir / "devices")], "{name}.jinja2"),
            "device-type": ([str(tmpdir / "device-types")], "{name}.jinja2"),
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

    assert isinstance(File("device").loader(), jinja2.loaders.FileSystemLoader) is True
    assert File("device").loader().searchpath == [
        str(tmpdir / "devices"),
        str(tmpdir / "device-types"),
    ]


def test_file_device_type(mocker, tmpdir):
    mocker.patch(
        "lava_server.files.File.KINDS",
        {"device-type": ([str(tmpdir / "0"), str(tmpdir / "1")], "{name}.jinja2")},
    )
    assert File("device-type", "hello").exists() is False

    # Test fallback
    (tmpdir / "1").mkdir()
    (tmpdir / "1" / "hello.jinja2").write("base")
    assert File("device-type", "hello").read() == "base"

    # Create the file
    File("device-type", "hello").write("new version")
    assert File("device-type", "hello").exists() is True
    assert File("device-type", "hello").read() == "new version"

    ret = File("device-type").list("*.yaml")
    assert len(ret) == 0

    ret = File("device-type").list("*.jinja2")
    assert len(ret) == 1
    assert ret[0] == "hello.jinja2"

    assert File("device-type").loader().searchpath == [
        str(tmpdir / "0"),
        str(tmpdir / "1"),
    ]


def test_file_env(mocker, tmpdir):
    mocker.patch(
        "lava_server.files.File.KINDS",
        {"env": [str(tmpdir / "{name}/env.yaml"), str(tmpdir / "env.yaml")]},
    )
    assert File("env", "worker01").exists() is False

    # Test fallback
    (tmpdir / "worker01").mkdir()
    (tmpdir / "worker01" / "env.yaml").write("base")
    assert File("env", "worker01").read() == "base"

    # Create the file
    File("env", "worker01").write("new version")
    assert File("env", "worker01").exists() is True
    assert File("env", "worker01").read() == "new version"


def test_file_errors(mocker, tmpdir):
    mocker.patch(
        "lava_server.files.File.KINDS",
        {
            "health-check": ([str(tmpdir / "0"), str(tmpdir / "1")], "{name}.jinja2"),
            "env": [str(tmpdir / "env")],
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
