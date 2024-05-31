# Copyright (C) 2024 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from unittest import TestCase
from unittest.mock import MagicMock

from lava_common.timeout import Timeout
from lava_dispatcher.shell import ShellCommand, ShellSession
from lava_dispatcher.utils.selectors import ShellSessionSelector


class TestSelectors(TestCase):
    def test_listen_multiple_feedbacks(self) -> None:
        log_mock_1 = MagicMock()
        log_mock_2 = MagicMock()
        timeout = Timeout("test-selectors", None)

        connection_1 = ShellSession(
            ShellCommand("sh -c 'echo one'", timeout, logger=log_mock_1)
        )
        self.addCleanup(connection_1.raw_connection.close, True)

        connection_2 = ShellSession(
            ShellCommand("sh -c 'echo two;sleep 60'", timeout, logger=log_mock_2)
        )
        self.addCleanup(connection_2.raw_connection.close, True)

        selector = ShellSessionSelector()
        selector.add_feedback_connection(connection_1, namespace="test")
        selector.add_feedback_connection(connection_2)

        with selector:
            selector.listen_feedback(0.2)

        log_mock_1.feedback.assert_called_once_with("one", namespace="test")
        log_mock_2.feedback.assert_called_once_with("two")

    def test_listen_feedback_instant(self) -> None:
        timeout = Timeout("test-selectors-instant", None)

        log_mock_1 = MagicMock()
        connection_1 = ShellSession(
            ShellCommand("sh -c 'echo test'", timeout, logger=log_mock_1)
        )
        self.addCleanup(connection_1.raw_connection.close, True)

        selector = ShellSessionSelector()
        selector.add_feedback_connection(connection_1, namespace="test")

        connection_1.raw_connection.wait()

        with selector:
            selector.listen_feedback_instant()

        log_mock_1.feedback.assert_called_once_with("test", namespace="test")
