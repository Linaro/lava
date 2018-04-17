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

from django.core.files import File
from django.core.files.storage import FileSystemStorage


class GzipFileSystemStorage(FileSystemStorage):

    def _open(self, name, mode='rb'):
        full_path = self.path(name)
        gzip_file = gzip.GzipFile(full_path, mode)
        gzip_file.name = full_path
        return File(gzip_file)
