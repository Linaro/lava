# Copyright (C) 2014 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
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
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import atexit
import os
import shutil
import tempfile


def rmtree(directory):
    """
    Wrapper around shutil.rmtree to remove a directory tree while ignoring most errors.
    If called on a symbolic link, this function will raise a RuntimeError.
    """
    try:
        shutil.rmtree(directory)
    except OSError as exc:
        raise RuntimeError("Error when trying to remove '%s': %s" % (directory, exc))


def mkdtemp(autoremove=True, basedir='/tmp'):
    """
    returns a temporary directory that's deleted when the process exits

    """
    tmpdir = tempfile.mkdtemp(dir=basedir)
    os.chmod(tmpdir, 0o755)
    if autoremove:
        atexit.register(rmtree, tmpdir)
    return tmpdir
