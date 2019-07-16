# -*- coding: utf-8 -*-
# Copyright (C) 2014 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of Linaro Django XMLRPC.
#
# Linaro Django XMLRPC is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Linaro Django XMLRPC is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Linaro Django XMLRPC.  If not, see <http://www.gnu.org/licenses/>.

from django.contrib import admin

from linaro_django_xmlrpc.models import AuthToken


class AuthTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "description", "created_on", "last_used_on")


admin.site.register(AuthToken, AuthTokenAdmin)
