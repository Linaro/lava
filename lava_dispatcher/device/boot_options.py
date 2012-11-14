# Copyright (C) 2012 Linaro Limited
#
# Author: Andy Doan <andy.doan@linaro.org>
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


class BootOption(object):
    """
    Parses items from a config ini section into an options object.
    """
    def __init__(self, section, items):
        self.name = section
        self.value = None
        self.allowed = None
        for item in items:
            if item[0] == 'default':
                self.value = item[1]
            elif item[0] == 'allowed':
                self.allowed = [x.strip() for x in item[1].split(',')]
            else:
                logging.warn('section(%s) contains unknown item: %s' %
                    (section, item))

    def valid(self, option):
        if self.allowed:
            return option in self.allowed
        # if no "allowed" value is set, then we can accept anything
        return True


def as_dict(target):
    options = {}
    for opt in target.config.boot_options:
        if opt in target.config.cp.sections():
            options[opt] = BootOption(opt, target.config.cp.items(opt))
        else:
            logging.warn('no boot option config section for: %s' % opt)

    for opt in target.boot_options:
        keyval = opt.split('=')
        if len(keyval) != 2:
            logging.warn("Invalid boot option format: %s" % opt)
        elif keyval[0] not in options:
            logging.warn("Invalid boot option: %s" % keyval[0])
        elif not options[keyval[0]].valid(keyval[1]):
            logging.warn("Invalid boot option value: %s" % opt)
        else:
            options[keyval[0]].value = keyval[1]

    return options


def as_string(target, join_pattern):
    """
    pulls the options into a string via the join_pattern. The join pattern
    can be something like "%s=%s"
    """
    options = as_dict(target)

    cmd = ''
    for option in options.values():
        if option.value:
            cmd += join_pattern % (option.name, option.value)
    return cmd
