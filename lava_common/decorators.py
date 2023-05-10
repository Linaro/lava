# Copyright (C) 2019 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


# Decorator from nose.tools package
def nottest(f):
    f.__test__ = False
    return f
