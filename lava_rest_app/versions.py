# Copyright (C) 2018 Linaro Limited
#
# Author: Milosz Wasilewski <milosz.wasilewski@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

versions = ("v0.2", "v0.3")


def urlpattern():
    return "|".join(versions)
