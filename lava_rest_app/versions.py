# -*- coding: utf-8 -*-
# Copyright (C) 2018 Linaro Limited
#
# Author: Milosz Wasilewski <milosz.wasilewski@linaro.org>
#
# SPDX-License-Identifier: AGPL-3.0-only

versions = ("v0.1", "v0.2")


def urlpattern():
    return "|".join(versions)
