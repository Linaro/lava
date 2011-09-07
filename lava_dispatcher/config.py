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

from ConfigParser import ConfigParser, NoOptionError
import os
import StringIO


def load_config_paths(name):
    for directory in os.path.expanduser("~/.config"), '/etc/xdg', "config":
        path = os.path.join(directory, name)
        if os.path.isdir(path):
            yield path


def _read_into(path, cp):
    s = StringIO.StringIO()
    s.write('[DEFAULT]\n')
    s.write(open(path).read())
    s.seek(0)
    cp.readfp(s)


def _get_config(name, cp=None):
    """Read a config file named name + '.conf'.

    This checks and loads files from the source tree, site wide location and
    home directory -- in that order, so home dir settings override site
    settings which override source settings.
    """
    config_files = []
    for directory in load_config_paths('lava-dispatcher'):
        path = os.path.join(directory, '%s.conf' % name)
        if os.path.exists(path):
            config_files.append(path)
    config_files.reverse()
    if cp is None:
        cp = ConfigParser()
    print "About to read %s" % str(config_files)
    for path in config_files:
        _read_into(path, cp)
    return cp


class ConfigWrapper(object):
    def __init__(self, cp):
        self.cp = cp
    def get(self, key, default):
        try:
            return self.cp.get("DEFAULT", key)
        except NoOptionError:
            return default


def get_config(name):
    return ConfigWrapper(_get_config(name))


def get_machine_config(name):
    machine_config = _get_config("machines/%s" % name)
    cp = _get_config("board-defaults")
    _get_config("board-types/%s" % machine_config.get('DEFAULT', 'board_type'), cp)
    _get_config("machines/%s" % name, cp)
    return ConfigWrapper(cp)
