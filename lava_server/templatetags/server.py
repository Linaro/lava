# Copyright (C) 2023-present Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django import template
from django.conf import settings

register = template.Library()


if settings.MATOMO_URL and settings.MATOMO_SITE_ID:
    from matomo.templatetags.matomo_tags import tracking_code

    @register.inclusion_tag("matomo/tracking_code.html")
    def matomo():
        return tracking_code()

else:

    @register.simple_tag
    def matomo():
        return ""
