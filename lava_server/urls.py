# Copyright (C) 2010-2018 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.conf import settings
from django.conf.urls import include
from django.contrib import admin
from django.views.generic import TemplateView
from django.views.i18n import JavaScriptCatalog

from lava_results_app.api import ResultsAPI
from lava_scheduler_app.api import SchedulerAPI
from lava_scheduler_app.api.aliases import SchedulerAliasesAPI
from lava_scheduler_app.api.device_types import (
    SchedulerDeviceTypesAliasesAPI,
    SchedulerDeviceTypesAPI,
)
from lava_scheduler_app.api.devices import SchedulerDevicesAPI, SchedulerDevicesTagsAPI
from lava_scheduler_app.api.jobs import SchedulerJobsAPI
from lava_scheduler_app.api.tags import SchedulerTagsAPI
from lava_scheduler_app.api.workers import SchedulerWorkersAPI
from lava_server.api import LavaMapper
from lava_server.api.groups import GroupsAPI, GroupsPermissionsAPI
from lava_server.api.users import UsersAPI, UsersGroupsAPI, UsersPermissionsAPI
from lava_server.compat import url
from lava_server.views import (
    delete_remote_auth,
    healthz,
    index,
    me,
    prometheus,
    update_irc_settings,
    update_remote_auth,
    update_table_length_setting,
)
from linaro_django_xmlrpc.views import handler as linaro_django_xmlrpc_views_handler
from linaro_django_xmlrpc.views import help as linaro_django_xmlrpc_views_help

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
mapper.register(GroupsAPI, "auth.groups")
mapper.register(GroupsPermissionsAPI, "auth.groups.perms")
mapper.register(UsersAPI, "auth.users")
mapper.register(UsersGroupsAPI, "auth.users.groups")
mapper.register(UsersPermissionsAPI, "auth.users.perms")

# Auth backends
auth_urls = [
    url(
        rf"^{settings.MOUNT_POINT}accounts/",
        include("django.contrib.auth.urls"),
    )
]

if (
    "allauth.account.auth_backends.AuthenticationBackend"
    in settings.AUTHENTICATION_BACKENDS
):
    auth_urls.append(
        url(
            rf"^{settings.MOUNT_POINT}accounts/",
            include("allauth.urls"),
        )
    )

# Root URL patterns
urlpatterns = [
    url(
        r"^robots\.txt$",
        TemplateView.as_view(template_name="robots.txt"),
        name="robots",
    ),
    url(
        rf"^{settings.MOUNT_POINT}v1/healthz/$",
        healthz,
        name="lava.healthz",
    ),
    url(
        rf"^{settings.MOUNT_POINT}v1/prometheus/$",
        prometheus,
        name="lava.prometheus",
    ),
    url(
        rf"^{settings.MOUNT_POINT}$",
        index,
        name="lava.home",
    ),
    url(
        rf"^{settings.MOUNT_POINT}me/$",
        me,
        name="lava.me",
    ),
    url(
        rf"^{settings.MOUNT_POINT}update-irc-settings/$",
        update_irc_settings,
        name="lava.update_irc_settings",
    ),
    url(
        rf"^{settings.MOUNT_POINT}update-remote-auth/$",
        update_remote_auth,
        name="lava.update_remote_auth",
    ),
    url(
        r"^{mount_point}delete-remote-auth/(?P<pk>[0-9]+|[0-9]+\.[0-9]+)/$".format(
            mount_point=settings.MOUNT_POINT
        ),
        delete_remote_auth,
        name="lava.delete_remote_auth",
    ),
    url(
        r"^{mount_point}update-table-length-setting/$".format(
            mount_point=settings.MOUNT_POINT
        ),
        update_table_length_setting,
        name="lava.update_table_length_setting",
    ),
    *auth_urls,
    url(r"^admin/jsi18n", JavaScriptCatalog.as_view()),
    url(
        rf"^{settings.MOUNT_POINT}admin/",
        admin.site.urls,
    ),
    # RPC endpoints
    url(
        rf"^{settings.MOUNT_POINT}RPC2/?",
        linaro_django_xmlrpc_views_handler,
        name="lava.api_handler",
        kwargs={"mapper": mapper, "help_view": "lava.api_help"},
    ),
    url(
        rf"^{settings.MOUNT_POINT}api/help/$",
        linaro_django_xmlrpc_views_help,
        name="lava.api_help",
        kwargs={"mapper": mapper},
    ),
    url(
        rf"^{settings.MOUNT_POINT}api/",
        include("linaro_django_xmlrpc.urls"),
    ),
    url(
        rf"^{settings.MOUNT_POINT}results/",
        include("lava_results_app.urls"),
    ),
    url(
        rf"^{settings.MOUNT_POINT}scheduler/",
        include("lava_scheduler_app.urls"),
    ),
    # REST API
    url(
        rf"^{settings.MOUNT_POINT}api/",
        include("lava_rest_app.urls"),
    ),
]

if settings.OIDC_ENABLED:
    urlpatterns.append(
        url(
            rf"^{settings.MOUNT_POINT}oidc/",
            include("mozilla_django_oidc.urls"),
        )
    )

if settings.USE_DEBUG_TOOLBAR:
    import debug_toolbar

    urlpatterns.append(url(r"^__debug__/", include(debug_toolbar.urls)))
