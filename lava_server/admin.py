from django.contrib import admin
from django.contrib.admin.models import LogEntry


class LogEntryAdmin(admin.ModelAdmin):
    def get_action_flag_display(self, obj):
        if obj.is_addition():
            return "+"
        elif obj.is_change():
            return "~"
        else:
            return "x"
        return obj.get_action_flag_display()
    list_display = ('action_time', 'user', 'content_type', 'object_repr',
                    'change_message', 'get_action_flag_display')
    list_filter = ('action_time', 'user')


admin.site.register(LogEntry, LogEntryAdmin)
