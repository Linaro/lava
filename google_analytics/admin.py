from django.conf import settings
from django.contrib import admin

from google_analytics.models import Analytic


class AnalyticAdmin(admin.ModelAdmin):
    list_display = ('site', 'analytics_code',)


if getattr(settings, 'GOOGLE_ANALYTICS_MODEL', False):
    admin.site.register(Analytic, AnalyticAdmin)
