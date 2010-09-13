"""
URL mappings for the Dashboard application

Those mappings are only effective during testing
"""
from django.conf.urls.defaults import *

from dashboard_app import urls
from dashboard_app.views import auth_test

# Start with empty pattern list 
urlpatterns = patterns('')
# Append original urls (we don't want to alter them)
urlpatterns += urls.urlpatterns
# Append our custom extra urls
urlpatterns += patterns('',
        url(r'^auth-test/', auth_test),
       )
