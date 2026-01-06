#
# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import time
from functools import wraps
from typing import TYPE_CHECKING, overload

from lava_common.log import YAMLLogger

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any, ParamSpec, TypeVar

    P = ParamSpec("P")
    R = TypeVar("R")


def replace_exception(
    cls_from: type[BaseException], cls_to: type[BaseException], limit: int = 2048
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def replace_exception_wrapper(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def function_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except cls_from as exc:
                raise cls_to(str(exc)[:limit])

        return function_wrapper

    return replace_exception_wrapper


def _get_object_logger(*args: Any) -> YAMLLogger | None:
    if len(args) < 1:
        return None

    try:
        self_arg = args[0]
    except IndexError:
        return None

    try:
        logger = self_arg.logger
    except AttributeError:
        return None

    if not isinstance(logger, YAMLLogger):
        return None

    return logger


@overload
def retry(
    exception: type[Exception],
    expected: None = None,
    retries: int = 3,
    delay: int = 1,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    ...


@overload
def retry(
    exception: type[Exception],
    expected: type[Exception] = Exception,
    retries: int = 3,
    delay: int = 1,
) -> Callable[[Callable[P, R]], Callable[P, R | None]]:
    ...


def retry(
    exception: type[Exception] | None = None,
    expected: type[Exception] | None = None,
    retries: int = 3,
    delay: int = 1,
) -> Callable[[Callable[P, R]], Callable[P, R | None]]:
    """
    A decorator to retry a function call if it raises a specified exception.
    :param exception: The exception to catch and retry on. Defaults to None.
    :param expected: The exception that shouldn't trigger a retry. Defaults to None.
    :param retries: Number of retry attempts. Defaults to 3.
    :param delay: Delay in seconds between retries. Defaults to 1.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        if exception is None:
            raise Exception("No exception provided for retrying")
        if expected is not None and issubclass(exception, expected):
            raise Exception(
                "'exception' shouldn't be a subclass of 'expected' exception"
            )

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = _get_object_logger(*args)

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
                    if logger is not None:
                        logger.error(
                            f"{str(exc)}: {attempt + 1} of {retries} attempts."
                        )
                    if attempt == int(retries) - 1:
                        raise
                    attempt += 1
                    time.sleep(delay)

        return wrapper

    return decorator
