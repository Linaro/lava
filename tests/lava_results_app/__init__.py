# Copyright (C) 2019 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import unittest

from lava_scheduler_app.models import Device


def suite():
    return unittest.TestLoader().discover(
        "tests.lava_results_app", pattern="*.py", top_level_dir="lava_results_app"
    )
