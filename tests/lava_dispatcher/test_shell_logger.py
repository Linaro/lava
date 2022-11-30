# Copyright (C) 2022 Collabora Limited
#
# Author: Igor Ponomarev <igor.ponomarev@collabora.com>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <http://www.gnu.org/licenses>.
from __future__ import annotations

from unittest import TestCase
from unittest.mock import MagicMock, Mock

from lava_dispatcher.shell import ShellLogger


class TestShellLogger(TestCase):
    def setUp(self) -> None:
        # Create mocked shell logger
        self.mock_logger = MagicMock()
        self.target_mock: Mock = self.mock_logger.target
        self.shell_logger = ShellLogger(self.mock_logger)

    def test_newline_separators(self) -> None:
        self.shell_logger.write(
            "Lorem ipsum dolor sit amet,\nconsectetur adipiscing elit,"
        )

        # Only one line should be logged
        self.assertEqual(self.target_mock.call_count, 1)
        self.target_mock.assert_called_with("Lorem ipsum dolor sit amet,\n")

        self.shell_logger.flush(force=True)
        # After flushing a second line should be logged
        self.assertEqual(self.target_mock.call_count, 2)
        self.target_mock.assert_called_with("consectetur adipiscing elit,")

    def test_unfishished_lines(self) -> None:
        self.shell_logger.write("Lorem ipsum dolor sit amet, ")
        # Nothing should be flushed
        self.target_mock.assert_not_called()

        self.shell_logger.write("consectetur adipiscing elit,")
        # Nothing should be flushed still
        self.target_mock.assert_not_called()

        self.shell_logger.flush(force=True)
        # Should be flushed once
        self.assertEqual(self.target_mock.call_count, 1)
        self.target_mock.assert_called_with(
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit,"
        )

    def test_carriage_return_separators(self) -> None:
        self.shell_logger.write("Lorem ipsum dolor sit amet,\r")
        # One carriage return should not be a line end
        self.target_mock.assert_not_called()

        self.shell_logger.write("consectetur adipiscing elit, ")
        # This should finish the previous line
        # and write output once
        self.target_mock.assert_called_once()
        self.target_mock.assert_called_with("Lorem ipsum dolor sit amet,\r")

        # Test \r\n fragment
        self.shell_logger.write("sed do eiusmod tempor incididunt ut\r")
        # Nothing should be flushed
        self.target_mock.assert_called_once()

        self.shell_logger.write("\nlabore et dolore magna aliqua.")
        # This should only add one single line to log
        self.assertEqual(self.target_mock.call_count, 2)
        self.target_mock.assert_called_with(
            "consectetur adipiscing elit, sed do eiusmod tempor incididunt ut\r\n"
        )

        self.shell_logger.flush(force=True)
        # This should finish the line.
        self.assertEqual(self.target_mock.call_count, 3)
        self.target_mock.assert_called_with("labore et dolore magna aliqua.")

    def test_gitlab_collapsible_sections(self) -> None:
        # Gitlab's collapsible sections use \r\x1b[0K
        # Test that even if \r and \x1b gets separated
        # the line separation is correct
        self.shell_logger.write("\x1b[0Ksection_start:1560896352:my_first_section\r")
        self.shell_logger.write("\x1b[0KHeader of the 1st collapsible section\r\n")
        self.shell_logger.write("this line should be hidden when collapsed\n")
        self.shell_logger.write(
            "\x1b[0Ksection_end:1560896353:my_first_section\r\x1b[0K\r\n"
        )

        # 5 lines should be logged
        self.assertEqual(self.target_mock.call_count, 5)
        self.target_mock.assert_called_with("\x1b[0K\r\n")
