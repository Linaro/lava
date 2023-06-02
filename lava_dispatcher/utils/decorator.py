#
# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

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
