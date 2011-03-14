import os
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'dashboard_server.settings.debian'

import django.core.handlers.wsgi

application = django.core.handlers.wsgi.WSGIHandler()
