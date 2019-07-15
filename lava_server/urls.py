# -*- coding: utf-8 -*-
# Copyright (C) 2010-2018 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA.  If not, see <http://www.gnu.org/licenses/>.

import contextlib

from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin
from linaro_django_xmlrpc.views import handler as linaro_django_xmlrpc_views_handler
from linaro_django_xmlrpc.views import help as linaro_django_xmlrpc_views_help
from django.views.i18n import javascript_catalog

from lava_results_app.api import ResultsAPI
from lava_scheduler_app.api import SchedulerAPI
from lava_scheduler_app.api.aliases import SchedulerAliasesAPI
from lava_scheduler_app.api.devices import SchedulerDevicesAPI, SchedulerDevicesTagsAPI
from lava_scheduler_app.api.device_types import (
    SchedulerDeviceTypesAPI,
    SchedulerDeviceTypesAliasesAPI,
)
from lava_scheduler_app.api.jobs import SchedulerJobsAPI
from lava_scheduler_app.api.tags import SchedulerTagsAPI
from lava_scheduler_app.api.workers import SchedulerWorkersAPI

from lava_server.api import LavaMapper
from lava_server.views import index, me, update_irc_settings

handler403 = "lava_server.views.permission_error"
handler500 = "lava_server.views.server_error"

# Enable admin stuff
admin.autodiscover()

# Create the XMLRPC mapper
mapper = LavaMapper()
mapper.register_introspection_methods()
mapper.register(ResultsAPI, "results")
mapper.register(SchedulerAPI, "scheduler")
mapper.register(SchedulerAliasesAPI, "scheduler.aliases")
mapper.register(SchedulerDevicesAPI, "scheduler.devices")
mapper.register(SchedulerDevicesTagsAPI, "scheduler.devices.tags")
mapper.register(SchedulerDeviceTypesAPI, "scheduler.device_types")
mapper.register(SchedulerDeviceTypesAliasesAPI, "scheduler.device_types.aliases")
mapper.register(SchedulerJobsAPI, "scheduler.jobs")
mapper.register(SchedulerTagsAPI, "scheduler.tags")
mapper.register(SchedulerWorkersAPI, "scheduler.workers")


# Root URL patterns
urlpatterns = [
    url(
        r"^robots\.txt$",
        TemplateView.as_view(template_name="robots.txt"),
        name="robots",
    ),
    url(
        r"^{mount_point}$".format(mount_point=settings.MOUNT_POINT),
        index,
        name="lava.home",
    ),
    url(
        r"^{mount_point}me/$".format(mount_point=settings.MOUNT_POINT),
        me,
        name="lava.me",
    ),
    url(
        r"^{mount_point}update-irc-settings/$".format(mount_point=settings.MOUNT_POINT),
        update_irc_settings,
        name="lava.update_irc_settings",
    ),
    url(
        r"^{mount_point}accounts/".format(mount_point=settings.MOUNT_POINT),
        include("django.contrib.auth.urls"),
    ),
    url(r"^admin/jsi18n", javascript_catalog),
    url(
        r"^{mount_point}admin/".format(mount_point=settings.MOUNT_POINT),
        admin.site.urls,
    ),
    # RPC endpoints
    url(
        r"^{mount_point}RPC2/?".format(mount_point=settings.MOUNT_POINT),
        linaro_django_xmlrpc_views_handler,
        name="lava.api_handler",
        kwargs={"mapper": mapper, "help_view": "lava.api_help"},
    ),
    url(
        r"^{mount_point}api/help/$".format(mount_point=settings.MOUNT_POINT),
        linaro_django_xmlrpc_views_help,
        name="lava.api_help",
        kwargs={"mapper": mapper},
    ),
    url(
        r"^{mount_point}api/".format(mount_point=settings.MOUNT_POINT),
        include("linaro_django_xmlrpc.urls"),
    ),
    url(
        r"^{mount_point}results/".format(mount_point=settings.MOUNT_POINT),
        include("lava_results_app.urls"),
    ),
    url(
        r"^{mount_point}scheduler/".format(mount_point=settings.MOUNT_POINT),
        include("lava_scheduler_app.urls"),
    ),
    # REST API
    url(
        r"^{mount_point}api/".format(mount_point=settings.MOUNT_POINT),
        include("lava_rest_app.urls"),
    ),
]

if settings.USE_DEBUG_TOOLBAR:
    import debug_toolbar

    urlpatterns.append(url(r"^__debug__/", include(debug_toolbar.urls)))

with contextlib.suppress(ImportError):
    from hijack.urls import urlpatterns as hijack_urlpatterns

    urlpatterns.append(url(r"^hijack/", include(hijack_urlpatterns)))
