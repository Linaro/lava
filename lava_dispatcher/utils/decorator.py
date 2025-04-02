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
    exception: Exception = None,
    expected: Exception = None,
    retries: int = 3,
    delay: int = 1,
):
    """
    A decorator to retry a function call if it raises a specified exception.
    :param exception: The exception to catch and retry on. Defaults to None.
    :param expected: The exception that shouldn't trigger a retry. Defaults to None.
    :param retries: Number of retry attempts. Defaults to 3.
    :param delay: Delay in seconds between retries. Defaults to 1.
    """

    def decorator(func):
        if exception is None:
            raise Exception("No exception provided for retrying")
        if expected is not None and issubclass(exception, expected):
            raise Exception(
                f"'exception' shouldn't be a subclass of 'expected' exception"
            )

        def wrapper(*args, **kwargs):
            logger = logging.getLogger("dispatcher")
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
