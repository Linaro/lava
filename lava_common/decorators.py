# Copyright (C) 2019 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, TypeVar

    F = TypeVar("F", bound=Any)


# Decorator from nose.tools package
def nottest(f: F) -> F:
    f.__test__ = False
    return f
