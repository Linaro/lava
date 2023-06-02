# Copyright (C) 2020-present Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lava_server.settings.prod")

app = Celery("lava_server")
# Import from django settings, prefixed with CELERY_
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
