# -*- coding: utf-8 -*-
# Copyright (C) 2011-2018 Linaro Limited
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

import contextlib
import lzma
import pathlib
import struct

PACK_FORMAT = "=Q"
PACK_SIZE = struct.calcsize(PACK_FORMAT)


def _build_index(directory):
    with open_logs(directory) as f_log:
        with open(str(directory / "output.idx"), "wb") as f_idx:
            f_idx.write(struct.pack(PACK_FORMAT, 0))
            line = f_log.readline()
            while line:
                f_idx.write(struct.pack(PACK_FORMAT, f_log.tell()))
                line = f_log.readline()


def _get_line_offset(f_idx, line):
    f_idx.seek(PACK_SIZE * line, 0)
    data = f_idx.read(PACK_SIZE)
    if data:
        return struct.unpack(PACK_FORMAT, data)[0]
    else:
        return None


def line_count(f_idx):
    return int(f_idx.tell() / PACK_SIZE)


def open_logs(dir_name):
    directory = pathlib.Path(dir_name)
    with contextlib.suppress(FileNotFoundError):
        return open(str(directory / "output.yaml"), "rb")
    return lzma.open(str(directory / "output.yaml.xz"), "rb")


def read_logs(dir_name, start=0, end=None):
    directory = pathlib.Path(dir_name)

    # Only create the index if needed
    if start == 0 and end is None:
        with open_logs(directory) as f_log:
            return f_log.read().decode("utf-8")

    # Create the index
    if not (directory / "output.idx").exists():
        _build_index(directory)
    # use it now
    with open(str(directory / "output.idx"), "rb") as f_idx:
        start_offset = _get_line_offset(f_idx, start)
        if start_offset is None:
            return ""
        with open_logs(directory) as f_log:
            f_log.seek(start_offset)
            if end is None:
                return f_log.read().decode("utf-8")
            end_offset = _get_line_offset(f_idx, end)
            if end_offset is None:
                return f_log.read().decode("utf-8")
            if end_offset <= start_offset:
                return ""
            return f_log.read(end_offset - start_offset).decode("utf-8")


def size_logs(dir_name):
    directory = pathlib.Path(dir_name)
    with contextlib.suppress(FileNotFoundError):
        return (directory / "output.yaml").stat().st_size
    with contextlib.suppress(FileNotFoundError, ValueError):
        return int((directory / "output.yaml.size").read_text(encoding="utf-8"))
    return None


def write_logs(f_log, f_idx, line):
    f_idx.write(struct.pack(PACK_FORMAT, f_log.tell()))
    f_idx.flush()
    f_log.write(line)
    f_log.flush()
