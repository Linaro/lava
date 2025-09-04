#
# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@contextmanager
def chdir(path: str | Path) -> Iterator[None]:
    pwd: str | None = None
    try:
        pwd = os.getcwd()
        os.chdir(path)
        yield
    finally:
        if pwd is not None:
            os.chdir(pwd)
