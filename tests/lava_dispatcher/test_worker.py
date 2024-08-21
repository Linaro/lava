# Copyright (C) 2024 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from os import waitpid
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from lava_dispatcher.worker import invoke_posix_spawn


class TestWorker(TestCase):
    def test_invoke_posix_spawn(self) -> None:
        with TemporaryDirectory() as tmp_dir_name:
            tmp_dir_path = Path(tmp_dir_name)
            test_file_path = tmp_dir_path / "test_stdout"

            pid = invoke_posix_spawn(
                ["echo", "test"],
                {},
                stdout_path=test_file_path,
            )

            _, exit_code = waitpid(pid, 0)

            self.assertEqual(exit_code, 0)
            self.assertEqual("test\n", test_file_path.read_text())
