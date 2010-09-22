# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

"""
Module with unit tests for launch_control.utils.filesystem module
"""

from launch_control.thirdparty.mocker import (
        ANY,
        MockerTestCase,
        expect,
        )
from launch_control.utils.filesystem import (
        read_lines_from_text_file_supressing_errors as fs_read_lines,
        read_text_file_supressing_errors as fs_read_text
        )


class FilesystemUtilsTestCase(MockerTestCase):

    def setUp(self):
        super(FilesystemUtilsTestCase, self).setUp()
        self.mocker.order()
        self.mock_builtin_open = self.mocker.replace("__builtin__.open")
        self.mock_gzip_open = self.mocker.replace("gzip.open")

    def mock_stream_for_pathname(self, pathname):
        if pathname.endswith('.gz'):
            return self.mock_gzip_open
        else:
            return self.mock_builtin_open

    def mock_file(self, pathname, content):
        mock_open = self.mock_stream_for_pathname(pathname)
        mock_stream = self.mocker.mock()
        expect(mock_open(pathname, 'rt')).result(mock_stream)
        expect(mock_stream.readlines()).result(content.splitlines(True))
        expect(mock_stream.close())

    def mock_exception_at_readlines(self, pathname, exception):
        mock_open = self.mock_stream_for_pathname(pathname)
        mock_stream = self.mocker.mock()
        expect(mock_open(pathname, 'rt')).result(mock_stream)
        expect(mock_stream.readlines()).throw(exception)
        expect(mock_stream.close())

    def mock_exception_at_open(self, pathname, exception):
        mock_open = self.mock_stream_for_pathname(pathname)
        mock_stream = self.mocker.mock()
        expect(mock_open(pathname, 'rt')).throw(exception)

    def test_empty_file(self):
        self.mock_file('file.txt', '')
        self.mocker.replay()
        self.assertEqual(fs_read_text('file.txt'), '')
    
    def test_file_noeol(self):
        self.mock_file('file.txt', 'content without newline')
        self.mocker.replay()
        self.assertEqual(fs_read_text('file.txt'), 'content without newline')

    def test_normal_file(self):
        self.mock_file('file.txt', 'line1\nline2\n')
        self.mocker.replay()
        self.assertEqual(fs_read_text('file.txt'), 'line1\nline2\n')

    def test_exceptions(self):
        for exception in [IOError, OSError]:
            self.mock_exception_at_open("file.txt", exception())
            self.mock_exception_at_readlines("file.txt", exception())
        self.mocker.replay()
        for i in range(4):
            self.assertEqual(fs_read_text('file.txt'), '')


