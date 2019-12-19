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

from lava_scheduler_app.logutils import read_logs, size_logs, write_logs


def test_read_logs_uncompressed(tmpdir):
    (tmpdir / "output.yaml").write_text("hello\nworld\nhow\nare\nyou", encoding="utf-8")
    assert read_logs(str(tmpdir)) == "hello\nworld\nhow\nare\nyou"  # nosec
    assert not (tmpdir / "output.idx").exists()  # nosec

    # If output.yaml exists, read_logs should use it
    with lzma.open(str(tmpdir / "output.yaml.xz"), "wb") as f_logs:
        f_logs.write("compressed".encode("utf-8"))
    assert read_logs(str(tmpdir)) == "hello\nworld\nhow\nare\nyou"  # nosec
    assert not (tmpdir / "output.idx").exists()  # nosec

    # Test the index
    assert read_logs(str(tmpdir), start=1) == "world\nhow\nare\nyou"  # nosec
    assert (tmpdir / "output.idx").exists()  # nosec
    assert read_logs(str(tmpdir), start=1, end=2) == "world\n"  # nosec
    assert read_logs(str(tmpdir), start=1, end=3) == "world\nhow\n"  # nosec
    assert read_logs(str(tmpdir), start=4, end=5) == "you"  # nosec
    assert read_logs(str(tmpdir), start=5, end=50) == ""  # nosec


def test_read_logs_compressed(tmpdir):
    with lzma.open(str(tmpdir / "output.yaml.xz"), "wb") as f_logs:
        f_logs.write("compressed\nor\nnot".encode("utf-8"))
    assert read_logs(str(tmpdir)) == "compressed\nor\nnot"  # nosec
    assert not (tmpdir / "output.idx").exists()  # nosec

    # Use the index
    assert read_logs(str(tmpdir), start=1) == "or\nnot"  # nosec
    assert (tmpdir / "output.idx").exists()  # nosec
    assert read_logs(str(tmpdir), start=1, end=2) == "or\n"  # nosec
    assert read_logs(str(tmpdir), start=1, end=20) == "or\nnot"  # nosec
    assert read_logs(str(tmpdir), start=2, end=2) == ""  # nosec
    assert read_logs(str(tmpdir), start=1, end=0) == ""  # nosec


def test_size_logs(tmpdir):
    with lzma.open(str(tmpdir / "output.yaml.xz"), "wb") as f_logs:
        f_logs.write("hello world\nhow are you?\n".encode("utf-8"))
    # "output.yaml.size" is missing
    assert size_logs(str(tmpdir)) is None  # nosec
    (tmpdir / "output.yaml.size").write_text("25", encoding="utf-8")
    assert size_logs(str(tmpdir)) == 25  # nosec

    with open(str(tmpdir / "output.yaml"), "wb") as f_logs:
        f_logs.write("hello world!\n".encode("utf-8"))
    assert size_logs(str(tmpdir)) == 13  # nosec


def test_write_logs(tmpdir):
    with open(str(tmpdir / "output.yaml"), "wb") as f_logs:
        with open(str(tmpdir / "output.idx"), "wb") as f_idx:
            write_logs(f_logs, f_idx, "hello world\n".encode("utf-8"))
            write_logs(f_logs, f_idx, "how are you?\n".encode("utf-8"))
    assert read_logs(str(tmpdir)) == "hello world\nhow are you?\n"  # nosec
    assert size_logs(str(tmpdir)) == 25  # nosec
    with open(str(tmpdir / "output.idx"), "rb") as f_idx:
        assert f_idx.read(8) == b"\x00\x00\x00\x00\x00\x00\x00\x00"  # nosec
        assert f_idx.read(8) == b"\x0c\x00\x00\x00\x00\x00\x00\x00"  # nosec
