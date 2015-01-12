# Copyright (C) 2014 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
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

import logging
import yaml


class YamlLogger(object):

    def __init__(self, name):
        """
        Logs written to the per action log must use the YamlLogger.
        """
        self.name = name
        self.description = "yaml logger"
        self.log = logging.getLogger("%s" % self.name)
        self.log.setLevel(logging.DEBUG)
        self.pattern = ' - id: "<LAVA_DISPATCHER>%(asctime)s"\n%(message)s'
        self.handler = None

    def log_message(self, message):
        if not message:
            return
        if type(message) is dict:
            for key, value in list(message.items()):
                self.log.debug("   %s: %s", key, value)
        else:
            self.log.debug("   log: \"%s\"", message)

    def debug(self, message):
        self.log_message(message)

    def set_handler(self, handler=None):
        if handler is not None:
            self.handler = handler
        else:
            self.handler = get_yaml_handler()
        self.handler.addFilter(logging.Filter(self.name))
        self.log.addHandler(self.handler)

    def remove_handler(self):
        if self.handler is not None:
            self.log.removeHandler(self.handler)
            self.handler.close()
            self.handler = None


def get_yaml_handler(filename=None, mode='w', encoding='utf-8'):
    pattern = ' - id: "<LAVA_DISPATCHER>%(asctime)s"\n%(message)s'
    if filename:
        if isinstance(filename, file):
            handler = logging.StreamHandler(filename)
        elif isinstance(filename, str):
            handler = logging.FileHandler(filename,
                                          mode=mode,
                                          encoding=encoding)
            handler.setFormatter(logging.Formatter(pattern))
    else:
        handler = logging.StreamHandler()
    return handler


class YamlFilter(logging.Filter):  # pylint: disable=too-few-public-methods
    """
    filters standard logs into structured logs
    """

    def filter(self, record):
        record.msg = yaml.dump(record.msg)
        return True


class StdLogger(object):  # pylint: disable=too-few-public-methods

    def __init__(self, name, filename):
        """
        Output for stdout (which is redirected to the oob_file by the
        scheduler) should use the ASCII logger.
        """
        self.name = name
        self.description = "std logger"
        self.log = logging.getLogger("%s" % name)
        self.log.setLevel(logging.INFO)
        self.handler = logging.StreamHandler(filename)
        self.formatter = logging.Formatter('"%(asctime)s"\n%(message)s')
        self.handler.setFormatter(self.formatter)

    def info(self, message):
        self.log.info(message)

    def debug(self, message):
        self.log.debug(message)
