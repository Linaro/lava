# Copyright (C) 2011-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import django

if django.VERSION < (3, 2):  # pragma: no cover
    default_app_config = "lava_scheduler_app.apps.LAVASchedulerConfig"
