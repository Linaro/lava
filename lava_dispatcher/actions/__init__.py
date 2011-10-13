#!/usr/bin/python

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

from glob import glob
import imp
import os


class classproperty(object):
    """Like the builtin @property, but binds to the class not instances."""

    def __init__(self, func):
        self.func = func

    def __get__(self, ob, cls):
        return self.func(cls)


class BaseAction(object):
    def __init__(self, context):
        self.context = context

    @property
    def client(self):
        return self.context.client

    @classproperty
    def command_name(cls):
        cls_name = cls.__name__
        if cls_name.startswith('cmd_'):
            return cls_name[4:]
        else:
            # This should never happen.  But it's not clear that raising an
            # AssertionError from this point would be useful either.
            return cls_name

    def test_name(self, **params):
        return self.command_name


class BaseAndroidAction(BaseAction):
    def __init__(self, context):
        self.context = context

    def check_sys_bootup(self):
        result_pattern = "([0-1])"
        cmd = "getprop sys.boot_completed"
        self.client.proc.sendline(cmd)
        id = self.client.proc.expect([result_pattern], timeout = 60)
        if id == 0:
            return True
        else:
            return False

def _find_commands(module):
    cmds = {}
    for name, cls in module.__dict__.iteritems():
        if name.startswith("cmd_"):
            cmds[cls.command_name] = cls
    return cmds

def get_all_cmds():
    cmds = {}
    cmd_path = os.path.dirname(os.path.realpath(__file__))
    for f in glob(os.path.join(cmd_path,"*.py")):
        module = imp.load_source("module", os.path.join(cmd_path,f))
        cmds.update(_find_commands(module))
    return cmds
