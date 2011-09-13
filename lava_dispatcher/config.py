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
import StringIO


default_config_path = os.path.join(
    os.path.dirname(__file__), 'default-config')


def load_config_paths(name):
    for directory in [os.path.expanduser("~/.config"),
                      "/etc/xdg", default_config_path]:
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
    if not config_files:
        raise Exception("no config files named %r found" % (name + ".conf"))
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
    def get(self, key):
        return self.cp.get("DEFAULT", key)
    def getint(self, key):
        return self.cp.getint("DEFAULT", key)


def get_config(name):
    return ConfigWrapper(_get_config(name))


def get_device_config(name):
    device_config = _get_config("devices/%s" % name)
    cp = _get_config("device-defaults")
    _get_config(
        "device-types/%s" % device_config.get('DEFAULT', 'device_type'), cp)
    _get_config("devices/%s" % name, cp)
    cp.set("DEFAULT", "hostname", name)
    return ConfigWrapper(cp)
