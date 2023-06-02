# Copyright (C) 2015-2018 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from functools import wraps

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from lava_results_app.models import Chart


def ownership_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        report_name = kwargs.get("name")
        chart = get_object_or_404(Chart, name=report_name)
        if chart.can_admin(request.user):
            return view_func(request, *args, **kwargs)
        else:
            raise PermissionDenied

    return wrapper
