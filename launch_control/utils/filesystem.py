# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

"""
Module with simple file system related utilities.
"""

import gzip


def read_text_file_supressing_errors(pathname):
    """
    Attempt to read the full content of a text file from the specified
    pathname. If this cannot be achieved because of IOError or OSError
    the error is silently suppressed and an empty string is returned
    instead.

    Note: this function depends on
    read_lines_from_text_file_supressing_errors(). It has some special
    considerations you should be aware of (newline translation and
    transparent gzip support).
    """
    return ''.join(read_lines_from_text_file_supressing_errors(pathname))


def read_lines_from_text_file_supressing_errors(pathname):
    """
    Attempt to read all lines of a text file from the specified
    pathname. If this cannot be achieved because of IOError or OSError
    the error is silently suppressed and an empty list is returned
    instead.

    Note: this function is accessing files in text mode so newline
    translation will happen on windows systems. That is, the file will
    always have \n style newlines, regardless of the actual platform.

    Note: In addition to reading plain text files this function supports
    transparent decompression of gzipped files that end with '.gz'
    extension.
    """
    stream = None
    try:
        if pathname.endswith(".gz"):
            stream = gzip.open(pathname, 'rt')
        else:
            stream = open(pathname, 'rt')
        return stream.readlines()
    except (IOError, OSError) as ex:
        return []
    finally:
        if stream is not None:
            stream.close()
