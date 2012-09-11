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
import logging


default_config_path = os.path.join(
    os.path.dirname(__file__), 'default-config')


def load_config_paths(name, config_dir):
    if config_dir is None:
        paths = [
            os.path.join(path, name) for path in [
                os.path.expanduser("~/.config"),
                "/etc/xdg",
                default_config_path]]
    else:
        paths = [config_dir, os.path.join(default_config_path, name)]
    for path in paths:
        if os.path.isdir(path):
            yield path


def _read_into(path, cp):
    s = StringIO.StringIO()
    s.write('[DEFAULT]\n')
    s.write(open(path).read())
    s.seek(0)
    cp.readfp(s)


def _get_config(name, config_dir, cp=None):
    """Read a config file named name + '.conf'.

    This checks and loads files from the source tree, site wide location and
    home directory -- in that order, so home dir settings override site
    settings which override source settings.
    """
    config_files = []
    for directory in load_config_paths('lava-dispatcher', config_dir):
        path = os.path.join(directory, '%s.conf' % name)
        if os.path.exists(path):
            config_files.append(path)
    if not config_files:
        raise Exception("no config files named %r found" % (name + ".conf"))
    config_files.reverse()
    if cp is None:
        cp = ConfigParser()
    logging.debug("About to read %s" % str(config_files))
    for path in config_files:
        _read_into(path, cp)
    return cp

_sentinel = object()

class ConfigWrapper(object):
    def __init__(self, cp, config_dir):
        self.cp = cp
        self.config_dir = config_dir
    def get(self, key, default=_sentinel):
        try:
            val = self.cp.get("DEFAULT", key)
            if default is not _sentinel and val == '':
                val = default
            return val
        except NoOptionError:
            if default is not _sentinel:
                return default
            else:
                raise
    def getint(self, key, default=_sentinel):
        try:
            return self.cp.getint("DEFAULT", key)
        except NoOptionError:
            if default is not _sentinel:
                return default
            else:
                raise

    def getboolean(self, key, default=True):
        try:
            return self.cp.getboolean("DEFAULT", key)
        except ConfigParser.NoOptionError:
            return default

def get_config(name, config_dir):
    return ConfigWrapper(_get_config(name, config_dir), config_dir)


def get_device_config(name, config_dir):
    device_config = _get_config("devices/%s" % name, config_dir)
    cp = _get_config("device-defaults", config_dir)
    _get_config(
        "device-types/%s" % device_config.get('DEFAULT', 'device_type'),
        config_dir, cp=cp)
    _get_config("devices/%s" % name, config_dir, cp=cp)
    cp.set("DEFAULT", "hostname", name)
    return ConfigWrapper(cp, config_dir)
