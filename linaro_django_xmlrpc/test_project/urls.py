from django.conf.urls import (
    patterns, url, include, handler500, handler404)

urlpatterns = patterns(
    '',
    url(r'', include('linaro_django_xmlrpc.urls')),
    url(r'^accounts/', include('django.contrib.auth.urls')),
)
