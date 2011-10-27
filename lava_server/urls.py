# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of LAVA Server.
#
# LAVA Server is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA Server is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA Server.  If not, see <http://www.gnu.org/licenses/>.

from django.conf import settings
from django.conf.urls.defaults import (
    handler404, handler500, include, patterns, url)
from django.contrib import admin
from staticfiles.urls import staticfiles_urlpatterns
from linaro_django_xmlrpc import urls as api_urls

from lava_server.extension import loader
from lava_server.views import index, me, version


# Enable admin stuff
admin.autodiscover()


# Root URL patterns
urlpatterns = patterns(
    '',
    url(r'^' + settings.APP_URL_PREFIX + r'$',
        index,
        name='lava.home'),
    url(r'^' + settings.APP_URL_PREFIX + r'me/$',
        me,
        name='lava.me'),
    url(r'^' + settings.APP_URL_PREFIX + r'version/$',
        version,
        name='lava.version_details'),
    url(r'^' + settings.APP_URL_PREFIX + r'accounts/',
        include('django.contrib.auth.urls')),
    url(r'^' + settings.APP_URL_PREFIX + r'admin/',
        include(admin.site.urls)),
    url(r'^' + settings.APP_URL_PREFIX + r'openid/',
        include('django_openid_auth.urls')),
    url(r'^' + settings.APP_URL_PREFIX + r'RPC2/',
        'linaro_django_xmlrpc.views.handler',
        name='lava.api_handler',
        kwargs={
            'mapper': loader.xmlrpc_mapper,
            'help_view': 'lava.api_help'}),
    url(r'^' + settings.APP_URL_PREFIX + r'api/help/$',
        'linaro_django_xmlrpc.views.help',
        name='lava.api_help',
        kwargs={
            'mapper': loader.xmlrpc_mapper}),
    url(r'^' + settings.APP_URL_PREFIX + r'api/',
        include(api_urls.token_urlpatterns)),
    # XXX: This is not needed but without it linaro-django-xmlrpc tests fail
    url(r'^' + settings.APP_URL_PREFIX + r'api/',
        include(api_urls.default_mapper_urlpatterns)),
    url(r'^' + settings.APP_URL_PREFIX + r'utils/markitup/',
        include('lava_markitup.urls')))


# Enable static files serving for development server
# NOTE: This can be removed in django 1.3
if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()


# Load URLs for extensions
loader.contribute_to_urlpatterns(urlpatterns)
