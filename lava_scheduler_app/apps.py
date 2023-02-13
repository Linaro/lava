# -*- coding: utf-8 -*-
# Copyright (C) 2016-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: AGPL-3.0-only

from django.apps import AppConfig


class LAVASchedulerConfig(AppConfig):
    name = "lava_scheduler_app"
    verbose_name = "lava_scheduler_app"

    def ready(self):
        import lava_scheduler_app.checks
        import lava_scheduler_app.signals
