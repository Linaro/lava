# Copyright (C) 2016-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.apps import AppConfig


class LAVASchedulerConfig(AppConfig):
    name = "lava_scheduler_app"
    verbose_name = "lava_scheduler_app"

    def ready(self):
        import lava_scheduler_app.checks
        from lava_scheduler_app.signals import register_scheduler_app_signals

        register_scheduler_app_signals()
