# Copyright (C) 2024 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from functools import partial
from selectors import EVENT_READ, DefaultSelector
from time import monotonic
from typing import TYPE_CHECKING

from pexpect import EOF, TIMEOUT

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from lava_dispatcher.shell import ShellSession


class ShellSessionSelector:
    def __init__(self) -> None:
        self.selector = DefaultSelector()

    def __enter__(self) -> ShellSessionSelector:
        return self

    def __exit__(self, *args: Any) -> None:
        self.selector.close()

    def add_feedback_connection(
        self, shell_session: ShellSession, namespace: str | None = None
    ) -> None:
        self.selector.register(
            shell_session.raw_connection.fileno(),
            EVENT_READ,
            partial(self._listen_feedback_nonblocking, shell_session, namespace),
        )

    def _listen_feedback_nonblocking(
        self, connection: ShellSession, namespace: str | None
    ) -> None:
        try:
            connection.raw_connection.logfile_read.is_feedback = True
            connection.raw_connection.logfile_read.namespace = namespace
            while connection.raw_connection.read_nonblocking(size=64_000, timeout=0):
                # Drain connection until there is nothing to read
                ...
        except TIMEOUT:
            return
        except EOF:
            self.selector.unregister(connection.raw_connection.fileno())
        finally:
            connection.raw_connection.logfile_read.is_feedback = False
            connection.raw_connection.logfile_read.namespace = None

    def listen_feedback(self, duration: int | float = 1) -> None:
        deadline = monotonic() + duration
        remaining_time = duration

        while (remaining_time := deadline - monotonic()) > 0.0:
            events = self.selector.select(remaining_time)
            for key, _ in events:
                callback: Callable[[], object] = key.data
                callback()

    def listen_feedback_instant(self) -> None:
        events = self.selector.select(0)

        for key, _ in events:
            callback: Callable[[], object] = key.data
            callback()
