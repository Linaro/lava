#
# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
from contextlib import contextmanager


@contextmanager
def chdir(path):
    pwd = None
    try:
        pwd = os.getcwd()
        os.chdir(path)
        yield
    finally:
        if pwd is not None:
            os.chdir(pwd)
