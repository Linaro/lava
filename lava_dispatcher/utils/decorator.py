# -*- coding: utf-8 -*-
#
# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses>.

from functools import wraps


def replace_exception(cls_from, cls_to, limit=2048):
    def replace_exception_wrapper(func):
        @wraps(func)
        def function_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except cls_from as exc:
                raise cls_to(str(exc)[:limit])

        return function_wrapper

    return replace_exception_wrapper
