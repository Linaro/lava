# Copyright (C) 2016-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured


class LAVASchedulerConfig(AppConfig):
    name = "lava_scheduler_app"
    verbose_name = "lava_scheduler_app"

    def ready(self):
        from django.conf import settings

        import lava_scheduler_app.checks  # pylint: disable=unused-import
        from lava_scheduler_app.signals import register_scheduler_app_signals

        register_scheduler_app_signals()

        # Validate HEALTH_FREQUENCY_HOURS
        hf = settings.HEALTH_FREQUENCY_HOURS
        if hf is not None and (
            isinstance(hf, bool) or not isinstance(hf, int) or hf <= 0
        ):
            raise ImproperlyConfigured(
                "HEALTH_FREQUENCY_HOURS must be a positive integer, got: %r" % hf
            )
