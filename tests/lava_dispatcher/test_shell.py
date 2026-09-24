# Copyright (C) 2026 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from unittest import TestCase
from unittest.mock import MagicMock

from lava_common.exceptions import LAVABug
from lava_common.timeout import Timeout
from lava_dispatcher.shell import ShellSession


class TestListenFeedback(TestCase):
    def create_shell_session(self, shell_cmd: str) -> ShellSession:
        session = ShellSession(
            shell_cmd,
            Timeout("test_shell", None),
            logger=MagicMock(),
        )
        self.addCleanup(session.finalise)
        return session

    def test_listen_feedback(self) -> None:
        session = self.create_shell_session(r"printf 'hello'")
        self.assertEqual(session.listen_feedback(timeout=5), len("hello"))

    # listen_feedback is called on every namespace when finalising the job.
    # Ensure that namespace sharing the same connection will not crash LAVA.
    def test_listen_feedback_after_finalise(self) -> None:
        session = self.create_shell_session(r"printf 'hello'")
        session.finalise()
        self.assertEqual(session.listen_feedback(timeout=5), 0)

    def test_listen_feedback_after_disconnect(self) -> None:
        session = self.create_shell_session(r"printf 'hello'")
        session.disconnect("testing")
        self.assertEqual(session.listen_feedback(timeout=5), 0)

    def test_listen_feedback_with_closed_raw_connection(self) -> None:
        session = self.create_shell_session(r"printf 'hello'")
        session.raw_connection.close(force=True)

        self.assertTrue(session.connected)
        self.assertEqual(session.listen_feedback(timeout=5), 0)


class TestPromptStr(TestCase):
    def create_shell_session(self, shell_cmd: str) -> ShellSession:
        session = ShellSession(
            shell_cmd,
            Timeout("test_shell", None),
            logger=MagicMock(),
        )
        self.addCleanup(session.finalise)
        return session

    def test_prompt_str_none_clears_list(self) -> None:
        session = self.create_shell_session("sleep 30")
        session.prompt_str = ["a", "b"]
        session.prompt_str = None
        self.assertEqual(session.prompt_str, [])

    def test_prompt_str_string_wrapped_in_list(self) -> None:
        session = self.create_shell_session("sleep 30")
        session.prompt_str = "root:"
        self.assertEqual(session.prompt_str, ["root:"])

    def test_prompt_str_list_replaces_list(self) -> None:
        session = self.create_shell_session("sleep 30")
        session.prompt_str = ["a"]
        session.prompt_str = ["b", "c"]
        self.assertEqual(session.prompt_str, ["b", "c"])

    def test_prompt_str_invalid_type_raises_lavabug(self) -> None:
        session = self.create_shell_session("sleep 30")
        with self.assertRaises(LAVABug):
            session.prompt_str = 42  # type: ignore[assignment]
