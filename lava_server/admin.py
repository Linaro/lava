# Copyright (C) 2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.conf import settings
from django.contrib import admin
from django.contrib.admin.models import LogEntry

# Fix for the admin "view site" link
admin.site.site_url = "/" + settings.MOUNT_POINT

# Customize titles
admin.site.site_title = "LAVA"
admin.site.site_header = "LAVA Administration"


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

    get_action_flag_display.short_description = "Action"

    list_display = (
        "action_time",
        "user",
        "content_type",
        "object_repr",
        "change_message",
        "get_action_flag_display",
    )
    list_filter = ("action_time", "user")


admin.site.register(LogEntry, LogEntryAdmin)
