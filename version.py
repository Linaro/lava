#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  version.py
#
#  Copyright 2014 Neil Williams <codehelp@debian.org>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#


import os
import subprocess
from lava_dispatcher.pipeline.utils.filesystem import version_tag

# pylint: disable=superfluous-parens,too-many-locals


def local_debian_package_version():
    changelog = 'debian/changelog'
    if os.path.exists(changelog):
        deb_version = subprocess.check_output((
            'dpkg-parsechangelog', '-l', changelog,
            '--show-field', 'Version')).strip().decode('utf-8')
        # example version returned would be '2016.11'
        return deb_version.split('-')[0]


def backup_version():
    if not os.path.exists("./.git/"):
        base = os.path.basename(os.getcwd())
        name_list = ['grep', 'name=', 'setup.py']
        name_data = subprocess.check_output(name_list).strip().decode('utf-8')
        name_data = name_data.replace("name=\'", '')
        name_data = name_data.replace("\',", '')
        return base.replace("%s-" % name_data, '')


def main():
    ret = version_tag()
    if not ret:
        ret = local_debian_package_version()
    if not ret:
        ret = backup_version()
    print(ret)
    return 0


if __name__ == '__main__':
    main()
