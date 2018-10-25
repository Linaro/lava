# Copyright (C) 2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import os
import subprocess  # nosec dpkg


def debian_package_arch(pkg):
    """
    Relies on Debian Policy rules for the existence of the
    changelog. Distributions not derived from Debian will
    return an empty string.
    """
    # release path
    changelog = '/usr/share/doc/%s/changelog.Debian.gz' % pkg
    if not os.path.exists(changelog):
        changelog = '/usr/share/doc/%s/changelog.gz' % pkg
    if os.path.exists(changelog):
        deb_arch = subprocess.check_output((  # nosec dpkg-query
            'dpkg-query', '-W', "-f=${Architecture}\n",
            "%s" % pkg)).strip().decode('utf-8', errors="replace")
        return deb_arch
    return ''


def debian_package_version(pkg, split):
    """
    Relies on Debian Policy rules for the existence of the
    changelog. Distributions not derived from Debian will
    return an empty string.
    """
    # release path
    changelog = '/usr/share/doc/%s/changelog.Debian.gz' % pkg
    if not os.path.exists(changelog):
        changelog = '/usr/share/doc/%s/changelog.gz' % pkg
    if os.path.exists(changelog):
        deb_version = subprocess.check_output((  # nosec dpkg-query
            'dpkg-query', '-W', "-f=${Version}\n",
            "%s" % pkg)).strip().decode('utf-8', errors="replace")
        # example version returned would be '2016.11'
        if split:
            return deb_version.split('-')[0]
        return deb_version
    return ''
