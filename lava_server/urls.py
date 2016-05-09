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

import imp
from django.conf import settings
from django.conf.urls import (
    handler404, include, url)
from django.contrib import admin
from linaro_django_xmlrpc import urls as api_urls
from linaro_django_xmlrpc.views import handler as linaro_django_xmlrpc_views_handler
from linaro_django_xmlrpc.views import help as linaro_django_xmlrpc_views_help
from django.views.i18n import javascript_catalog
from lava_server.extension import loader
from lava_server.views import index, me

handler403 = 'lava_server.views.permission_error'
handler500 = 'lava_server.views.server_error'

# Enable admin stuff
admin.autodiscover()


# Root URL patterns
urlpatterns = [
    url(r'^{mount_point}$'.format(mount_point=settings.MOUNT_POINT),
        index,
        name='lava.home'),
    url(r'^{mount_point}me/$'.format(mount_point=settings.MOUNT_POINT),
        me,
        name='lava.me'),

    url(r'^{mount_point}accounts/'.format(mount_point=settings.MOUNT_POINT),
        include('django.contrib.auth.urls')),

    url(r'^admin/jsi18n', javascript_catalog),
    url(r'^{mount_point}admin/'.format(mount_point=settings.MOUNT_POINT),
        include(admin.site.urls)),
    url(r'^{mount_point}RPC2/?'.format(mount_point=settings.MOUNT_POINT),
        linaro_django_xmlrpc_views_handler,
        name='lava.api_handler',
        kwargs={
            'mapper': loader.xmlrpc_mapper,
            'help_view': 'lava.api_help'}),
    url(r'^{mount_point}api/help/$'.format(mount_point=settings.MOUNT_POINT),
        linaro_django_xmlrpc_views_help,
        name='lava.api_help',
        kwargs={
            'mapper': loader.xmlrpc_mapper}),
    url(r'^{mount_point}api/'.format(mount_point=settings.MOUNT_POINT),
        include(api_urls.token_urlpatterns)),
    # XXX: This is not needed but without it linaro-django-xmlrpc tests fail
    url(r'^{mount_point}api/'.format(mount_point=settings.MOUNT_POINT),
        include(api_urls.default_mapper_urlpatterns))
]

try:
    import hijack
    from hijack.urls import urlpatterns as hijack_urlpatterns
    urlpatterns.append(url(r'^hijack/', include(hijack_urlpatterns)))
except ImportError:
    pass

try:
    imp.find_module('django_openid_auth')
    urlpatterns.append(
        url(r'^{mount_point}openid/'.format(mount_point=settings.MOUNT_POINT),
            include('django_openid_auth.urls')),
    )
except ImportError:
    pass


# Load URLs for extensions
loader.contribute_to_urlpatterns(urlpatterns, settings.MOUNT_POINT)
