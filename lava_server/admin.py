# -*- coding: utf-8 -*-
# Copyright (C) 2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
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

from django.conf import settings
from django.contrib import admin
from django.contrib.admin.models import LogEntry


# Fix for the admin "view site" link
admin.site.site_url = "/" + settings.MOUNT_POINT


class LogEntryAdmin(admin.ModelAdmin):

    def has_delete_permission(self, request, obj=None):
        return settings.ALLOW_ADMIN_DELETE

    def get_action_flag_display(self, obj):
        if obj.is_addition():
            return "+"
        elif obj.is_change():
            return "~"
        else:
            return "x"
        return obj.get_action_flag_display()

    get_action_flag_display.short_description = "Action"

    list_display = ('action_time', 'user', 'content_type', 'object_repr',
                    'change_message', 'get_action_flag_display')
    list_filter = ('action_time', 'user')


admin.site.register(LogEntry, LogEntryAdmin)
