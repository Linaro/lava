# Copyright (C) 2010, 2011 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Lava Dashboard.
#
# Lava Dashboard is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Lava Dashboard is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Lava Dashboard.  If not, see <http://www.gnu.org/licenses/>.

"""
Database models of the Dashboard application
"""

from __future__ import unicode_literals

import gzip

from django.core.files.storage import FileSystemStorage
from django.db import models


class GzipFileSystemStorage(FileSystemStorage):

    def _open(self, name, mode='rb'):
        full_path = self.path(name)
        gzip_file = gzip.GzipFile(full_path, mode)
        gzip_file.name = full_path
        return File(gzip_file)

    # This is a copy-paste-hack of FileSystemStorage._save
    def _save(self, name, content):
        full_path = self.path(name)

        directory = os.path.dirname(full_path)
        if not os.path.exists(directory):
            os.makedirs(directory)
        elif not os.path.isdir(directory):
            raise IOError("%s exists and is not a directory." % directory)

        # There's a potential race condition between get_available_name and
        # saving the file; it's possible that two threads might return the
        # same name, at which point all sorts of fun happens. So we need to
        # try to create the file, but if it already exists we have to go back
        # to get_available_name() and try again.

        while True:
            try:
                # This fun binary flag incantation makes os.open throw an
                # OSError if the file already exists before we open it.
                fd = os.open(full_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0))
                # This line, and the use of gz_file.write below, are the
                # changes from the original version of this.
                gz_file = gzip.GzipFile(fileobj=os.fdopen(fd, 'wb'))
                try:
                    locks.lock(fd, locks.LOCK_EX)
                    for chunk in content.chunks():
                        gz_file.write(chunk)
                finally:
                    locks.unlock(fd)
                    gz_file.close()
            except OSError as e:
                if e.errno == errno.EEXIST:
                    # Ooops, the file exists. We need a new file name.
                    name = self.get_available_name(name)
                    full_path = self.path(name)
                else:
                    raise
            else:
                # OK, the file save worked. Break out of the loop.
                break

        if settings.FILE_UPLOAD_PERMISSIONS is not None:
            os.chmod(full_path, settings.FILE_UPLOAD_PERMISSIONS)

        return name
