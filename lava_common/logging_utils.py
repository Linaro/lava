# Copyright (C) 2022 Collabora
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
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
from __future__ import annotations

from logging import Formatter, LogRecord
from json import dumps as json_dumps
from typing import FrozenSet, Optional, List


class JsonFormatter(Formatter):
    DEFAULT_KEYS: FrozenSet[str] = frozenset(
        (
            "args",
            "exc_info",  # Exception info
            "exc_text",
            "msg",  # Log message
            "name",  # Logger name
            "pathname",  # Log location
            "lineno",
            "stack_info",
            "levelname",  # Level name (DEBUG, INFO...)
        )
    )

    def __init__(self, *args, extra_keys: Optional[List[str]] = None, **kwargs):
        super().__init__(*args, **kwargs)
        if extra_keys is not None:
            extra_keys = set(extra_keys)
        else:
            extra_keys = set()

        self.allowed_keys = self.DEFAULT_KEYS | set(extra_keys)

    def filter_log_record_field(self, key: str, value: object) -> bool:
        if key not in self.allowed_keys:
            return False

        return True

    def format(self, record: LogRecord) -> str:
        logrecord_dict = {
            k: v
            for k, v in record.__dict__.items()
            if self.filter_log_record_field(k, v)
        }
        try:
            args = logrecord_dict.pop("args")
        except KeyError:
            args = ()

        logrecord_dict["msg"] %= args

        logrecord_dict["asctime"] = self.formatTime(record)

        return json_dumps(logrecord_dict)


def json_formatter(*args, **kwargs):
    return JsonFormatter(*args, **kwargs)
