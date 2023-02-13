# -*- coding: utf-8 -*-
# Copyright (C) 2014 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: AGPL-3.0-only

from django.contrib import admin

from linaro_django_xmlrpc.models import AuthToken


class AuthTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "description", "created_on", "last_used_on")


admin.site.register(AuthToken, AuthTokenAdmin)
