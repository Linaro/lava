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

from django.conf import settings
from importlib import import_module


class Logs:
    def line_count(self, job):
        raise NotImplementedError("Should implement this method")

    def open(self, job):
        raise NotImplementedError("Should implement this method")

    def read(self, job, start=0, end=None):
        raise NotImplementedError("Should implement this method")

    def size(self, job, start=0, end=None):
        raise NotImplementedError("Should implement this method")

    def write(self, job, line, output=None, idx=None):
        raise NotImplementedError("Should implement this method")


class LogsFilesystem(Logs):

    PACK_FORMAT = "=Q"
    PACK_SIZE = struct.calcsize(PACK_FORMAT)

    def __init__(self):
        self.index_filename = "output.idx"
        self.log_filename = "output.yaml"
        self.log_size_filename = "output.yaml.size"
        self.compressed_log_filename = "output.yaml.xz"
        super().__init__()

    def _build_index(self, job):
        directory = pathlib.Path(job.output_dir)
        with self.open(job) as f_log:
            with open(str(directory / self.index_filename), "wb") as f_idx:
                f_idx.write(struct.pack(self.PACK_FORMAT, 0))
                line = f_log.readline()
                while line:
                    f_idx.write(struct.pack(self.PACK_FORMAT, f_log.tell()))
                    line = f_log.readline()

    def _get_line_offset(self, f_idx, line):
        f_idx.seek(self.PACK_SIZE * line, 0)
        data = f_idx.read(self.PACK_SIZE)
        if data:
            return struct.unpack(self.PACK_FORMAT, data)[0]
        else:
            return None

    def line_count(self, job):
        st = (pathlib.Path(job.output_dir) / self.index_filename).stat()
        return int(st.st_size / self.PACK_SIZE)

    def open(self, job):
        directory = pathlib.Path(job.output_dir)
        with contextlib.suppress(FileNotFoundError):
            return open(str(directory / self.log_filename), "rb")
        return lzma.open(str(directory / self.compressed_log_filename), "rb")

    def read(self, job, start=0, end=None):
        directory = pathlib.Path(job.output_dir)

        # Only create the index if needed
        if start == 0 and end is None:
            with self.open(job) as f_log:
                return f_log.read().decode("utf-8")

        # Create the index
        if not (directory / self.index_filename).exists():
            self._build_index(job)
        # use it now
        with open(str(directory / self.index_filename), "rb") as f_idx:
            start_offset = self._get_line_offset(f_idx, start)
            if start_offset is None:
                return ""
            with self.open(job) as f_log:
                f_log.seek(start_offset)
                if end is None:
                    return f_log.read().decode("utf-8")
                end_offset = self._get_line_offset(f_idx, end)
                if end_offset is None:
                    return f_log.read().decode("utf-8")
                if end_offset <= start_offset:
                    return ""
                return f_log.read(end_offset - start_offset).decode("utf-8")

    def size(self, job):
        directory = pathlib.Path(job.output_dir)
        with contextlib.suppress(FileNotFoundError):
            return (directory / self.log_filename).stat().st_size
        with contextlib.suppress(FileNotFoundError, ValueError):
            return int((directory / self.log_size_filename).read_text(encoding="utf-8"))
        return None

    def write(self, job, line, output=None, idx=None):
        idx.write(struct.pack(self.PACK_FORMAT, output.tell()))
        idx.flush()
        output.write(line)
        output.flush()


logs_backend_str = settings.LAVA_LOG_BACKEND.rsplit(".", 1)
logs_class = getattr(import_module(logs_backend_str[0]), logs_backend_str[1])
logs_instance = logs_class()
