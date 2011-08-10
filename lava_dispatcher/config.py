# Copyright (C) 2011 Linaro Limited
#
# Author: Paul Larson <paul.larson@linaro.org>
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

from ConfigParser import ConfigParser
import os
from StringIO import StringIO

defaults = {
    'logging': StringIO(
'''
[logging]
level = INFO
destination = -
'''),
           }


def load_config_paths(name):
    for directory in os.path.expanduser("~/.config"), '/etc/xdg', "config":
        path = os.path.join(directory, name)
        if os.path.isdir(path):
            yield path


def get_config(name, fp=None):
    config_files = []
    for directory in load_config_paths('lava-dispatcher'):
        path = os.path.join(directory, '%s.conf' % name)
        print "Checking path %s" % str(path)
        if os.path.exists(path):
            config_files.append(path)
    config_files.reverse()
    if not fp:
        fp = ConfigParser(allow_no_value=True)
    if name in defaults:
        fp.readfp(defaults[name])
    print "About to read %s" % str(config_files)
    fp.read(config_files)
    return fp


def get_machine_config(name, image_type):
    fp = get_config("machines/%s" % name)
    print str(fp)
    fp = get_config("boards", fp)
    print str(fp)
    return fp
