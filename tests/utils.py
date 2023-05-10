# Copyright (C) 2016 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
from stat import S_IXUSR

from lava_dispatcher.utils.shell import _which_check


class DummyLogger:
    def info(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass

    def exception(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def results(self, *args, **kwargs):
        pass

    def marker(self, *args, **kwargs):
        pass

    def target(self, *args, **kwargs):
        pass


class RecordingLogger:
    def __init__(self):
        self.logs = []

    def info(self, *args, **kwargs):
        self.logs.append(("info", *args, {**kwargs}))

    def debug(self, *args, **kwargs):
        self.logs.append(("debug", *args, {**kwargs}))

    def exception(self, *args, **kwargs):
        self.logs.append(("exception", *args, {**kwargs}))

    def error(self, *args, **kwargs):
        self.logs.append(("error", *args, {**kwargs}))

    def warning(self, *args, **kwargs):
        self.logs.append(("warning", *args, {**kwargs}))

    def results(self, *args, **kwargs):
        self.logs.append(("results", *args, {**kwargs}))

    def marker(self, *args, **kwargs):
        self.logs.append(("marker", *args, {**kwargs}))

    def target(self, *args, **kwargs):
        self.logs.append(("target", *args, {**kwargs}))


def infrastructure_error(path):
    """
    Extends which into a check which sets default messages for Action validation,
    without needing to raise an Exception (which is slow).
    Use for quick checks on whether essential tools are installed and usable.
    """
    exefile = _which_check(path, match=os.path.isfile)
    if not exefile:
        return "Cannot find command '%s' in $PATH" % path
    # is the infrastructure call safe to make?
    if exefile and os.stat(exefile).st_mode & S_IXUSR != S_IXUSR:
        return "%s is not executable" % exefile
    return None


def infrastructure_error_multi_paths(path_list):
    """
    Similar to infrastructure_error, but accepts a list of paths.
    """
    for path in path_list:
        if infrastructure_error(path):
            return infrastructure_error(path)
    return None
