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
    def __init__(self, section, items, defval):
        self.name = section
        self.value = None
        self.allowed = None
        for item in items:
            if item[0] == 'default':
                self.value = item[1]
            elif item[0] == 'allowed':
                self.allowed = [x.strip() for x in item[1].split(',')]
            else:
                logging.warning('section(%s) contains unknown item: %s', section, item)
        if defval:
            self.value = defval

    def valid(self, option):
        if self.allowed:
            return option in self.allowed
        # if no "allowed" value is set, then we can accept anything
        return True


def as_dict(target, defaults={}):
    """
    converts the boot_options stanza for a device into a dictionary of
    key value pairs for the option and its value

    defaults - in some cases you need to override a default value specified
    in the device's config. For example for boot_options with master.py, the
    default for boot_cmds is boot_cmds. However, we really need to look at
    the deployment_data's boot_cmds for the default so that booting
    something like android will work.

    option - this is always false, unless a user specified boot_option
    has been set.
    """
    options = {}
    user_option = False
    for opt in target.config.boot_options:
        if opt in target.config.cp.sections():
            defval = defaults.get(opt, None)
            options[opt] = BootOption(opt, target.config.cp.items(opt), defval)
        else:
            logging.warning('no boot option config section for: %s', opt)

    for opt in target.boot_options:
        keyval = opt.split('=')
        if len(keyval) != 2:
            logging.warning("Invalid boot option format: %s", opt)
        elif keyval[0] not in options:
            logging.warning("Invalid boot option: %s", keyval[0])
        elif not options[keyval[0]].valid(keyval[1]):
            logging.warning("Invalid boot option value: %s", opt)
        else:
            user_option = True
            options[keyval[0]].value = keyval[1]

    return (options, user_option)


def as_string(target, join_pattern, defaults={}):
    """
    pulls the options into a string via the join_pattern. The join pattern
    can be something like "%s=%s"
    """
    options, user_option = as_dict(target, defaults)

    cmd = ''
    for option in options.values():
        if option.value:
            cmd += join_pattern % (option.name, option.value)
    return cmd
