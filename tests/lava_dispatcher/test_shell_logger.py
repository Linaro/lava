# Copyright (C) 2024 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from unittest import TestCase
from unittest.mock import MagicMock, call

from pexpect import EOF as pexpect_eof

from lava_common.timeout import Timeout
from lava_dispatcher.shell import ShellCommand


class TestShellLogger(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.logger_mock = MagicMock()

    def create_shell_command(self, shell_cmd: str) -> ShellCommand:
        return ShellCommand(
            shell_cmd,
            Timeout("test_shell_logger", None),
            logger=self.logger_mock,
        )

    def assert_logger_target_calls(
        self,
        input_logs: list[str],
        target_logs: list[str],
    ) -> None:
        input_mock = self.logger_mock.input
        target_mock = self.logger_mock.target
        with self.subTest("Check input logs"):
            input_mock.assert_has_calls([call(x) for x in input_mock])

        with self.subTest("Check target logs"):
            target_mock.assert_has_calls([call(x) for x in target_logs])

    # The pseudo TTY line mangling should be disabled
    # by preexec_fn. Only \r\n and \n will be split.
    def test_shell_output_newline(self) -> None:
        command = self.create_shell_command(r"printf 'foo\nbar'")
        command.expect(pexpect_eof)
        command.flush()
        self.assertEqual(command.exitstatus, 0)
        self.assert_logger_target_calls([], ["foo", "bar"])

    def test_shell_output_carriadge_return_newline(self) -> None:
        command = self.create_shell_command(r"printf 'foo\r\nbar'")
        command.expect(pexpect_eof)
        command.flush()
        self.assertEqual(command.exitstatus, 0)
        self.assert_logger_target_calls([], ["foo", "bar"])

    # Pseudo TTY echo mode should be disabled by preexec_fn.
    # Input should not be echoed back.
    def test_shell_input(self) -> None:
        command = self.create_shell_command(
            "sh -c 'read ONE TWO; echo \"$ONE, $TWO!\"'"
        )
        command.sendline("Hello World")
        command.expect(pexpect_eof)
        command.flush()
        self.assertEqual(command.exitstatus, 0)
        self.assert_logger_target_calls(
            ["Hello", "World"],
            [
                "Hello, World!",  # Actual output
            ],
        )

    def test_shell_input_two_inputs(self) -> None:
        command = self.create_shell_command(
            "sh -c 'read ONE; read TWO; echo \"$ONE, $TWO!\"'"
        )
        command.sendline("Hello")
        command.sendline("World")
        command.expect(pexpect_eof)
        command.flush()
        self.assertEqual(command.exitstatus, 0)
        self.assert_logger_target_calls(
            ["Hello", "World"],
            [
                "Hello, World!",  # Actual output
            ],
        )
