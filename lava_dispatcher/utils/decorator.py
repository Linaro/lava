#
# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import logging
import time
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


def retry(
    exception: Exception = Exception,
    expected: Exception = None,
    retries: int = 3,
    delay: int = 1,
):
    """
    Retry the wrapped function `retries` times if the `exception` is thrown
    :param exception: exception that trigger a retry attempt
    :param expected: expected exception
    :param retries: the number of times to retry
    :param delay: wait time after each attempt in seconds
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = logging.getLogger("dispatcher")
            if expected is not None and issubclass(exception, expected):
                raise Exception(
                    "'exception' shouldn't be a subclass of 'expected' exception"
                )
            for attempt in range(retries):
                try:
                    if expected is not None:
                        try:
                            return func(*args, **kwargs)
                        except expected:
                            return None
                    else:
                        return func(*args, **kwargs)
                except exception as exc:
                    logger.error(f"{str(exc)}: {attempt + 1} of {retries} attempts.")
                    if attempt == int(retries) - 1:
                        raise
                    attempt += 1
                    time.sleep(delay)

        return wrapper

    return decorator
