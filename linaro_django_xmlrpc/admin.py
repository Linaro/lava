from django.contrib import admin

from linaro_django_xmlrpc.models import AuthToken


class AuthTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'description', 'created_on', 'last_used_on')


admin.site.register(AuthToken, AuthTokenAdmin)
