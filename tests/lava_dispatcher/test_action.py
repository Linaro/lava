# Copyright (C) 2024 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
from time import monotonic as time_monotonic
from unittest import TestCase

from lava_dispatcher.action import Action


class TestActionRunCmd(TestCase):
    def setUp(self) -> None:
        self.action = Action()

    def test_simple_command_with_args(self) -> None:
        with self.assertLogs(self.action.logger, "DEBUG") as logs:
            ret = self.action.run_cmd(["printf", "Hello, world!"])

        self.assertEqual(ret, 0)
        self.assertIn(
            "Hello, world!",
            "".join(logs.output),
        )

    def test_no_args_command_with_spaces(self) -> None:
        true_path = which("true")
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            symlink_with_spaces_to_true = tmpdir_path / "with spaces true"
            symlink_with_spaces_to_true.symlink_to(true_path)

            ret = self.action.run_cmd([str(symlink_with_spaces_to_true)])

        self.assertEqual(ret, 0)

    def test_command_timeout(self) -> None:
        self.action.timeout.duration = 0.01

        start_time = time_monotonic()

        with self.assertRaises(self.action.command_exception), self.assertLogs(
            self.action.logger, "ERROR"
        ) as error_logs:
            self.action.run_cmd(["sleep", "10"])

        end_time = time_monotonic()

        self.assertIn(
            "Timed out after",
            "".join(error_logs.output),
        )

        self.assertLess(
            end_time - start_time,
            1.0,
        )

    def test_command_does_not_exist(self) -> None:
        non_existant_command = "THIS_COMMAND_does_NOT_exist"

        with self.assertRaises(self.action.command_exception), self.assertLogs(
            self.action.logger, "ERROR"
        ) as error_logs:
            self.action.run_cmd([non_existant_command])

        self.assertIn(
            non_existant_command,
            "".join(error_logs.output),
        )
