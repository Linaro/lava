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

    def run_shell_command(self, shell_cmd: str, input_line: str | None = None) -> None:
        command = ShellCommand(
            shell_cmd,
            Timeout("test_shell_logger", None),
            logger=self.logger_mock,
        )
        if input_line is not None:
            command.sendline(input_line)
        command.expect(pexpect_eof)
        command.flush()

    def assert_logger_target_calls(self, expected_log_fragments: list[str]) -> None:
        target_mock = self.logger_mock.target
        target_mock.assert_has_calls([call(x) for x in expected_log_fragments])

    # Because pexpect runs commands in pseudo TTY
    # it will mangle the output of commands.
    # \n -> \r\n
    # \r\n -> \r\r\n
    # ShellLogger is expected to split on both \r\n and \r\r\n
    def test_shell_output_newline(self) -> None:
        self.run_shell_command("printf 'foo\nbar'")
        self.assert_logger_target_calls(["foo", "bar"])

    def test_shell_output_carriadge_return_newline(self) -> None:
        self.run_shell_command("printf 'foo\r\nbar'")
        self.assert_logger_target_calls(["foo", "bar"])

    # Because of pseudo TTY all input will be echoed to output.
    # Also pexpect will log the input as well.
    # This means all input is double logged.
    # The pexpect input log will not mangle lines but pseudo TTY echo would.
    def test_shell_input(self) -> None:
        self.run_shell_command("true", input_line="foo")
        self.assert_logger_target_calls(["foo", "foo"])
