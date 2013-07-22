from django.db import models
from django.conf import settings
from django.contrib.sites.admin import SiteAdmin
from django.contrib.sites.models import Site
from django.contrib import admin

if getattr(settings, 'GOOGLE_ANALYTICS_MODEL', False):

    class Analytic(models.Model):
        site = models.ForeignKey(Site, unique=True)
        analytics_code = models.CharField(blank=True, max_length=100)

        def __unicode__(self):
            return u"%s" % (self.analytics_code)

    class AnalyticAdmin(admin.ModelAdmin):
        list_display = ('site', 'analytics_code',)
        #list_editable = ('site', 'analytics_code',)

    admin.site.register(Analytic, AnalyticAdmin)
