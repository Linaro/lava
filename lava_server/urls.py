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
from django.conf.urls import (
    handler404, include, patterns, url)
from django.contrib import admin
from longerusername.forms import AuthenticationForm
from linaro_django_xmlrpc import urls as api_urls

from lava_server.extension import loader
from lava_server.views import index, me, version


handler403 = 'lava_server.views.permission_error'
handler500 = 'lava_server.views.server_error'

# Enable admin stuff
admin.autodiscover()


# Root URL patterns
urlpatterns = patterns(
    '',
    url(r'^{mount_point}$'.format(mount_point=settings.MOUNT_POINT),
        index,
        name='lava.home'),
    url(r'^{mount_point}me/$'.format(mount_point=settings.MOUNT_POINT),
        me,
        name='lava.me'),

    # We need to override for login action to support longer usernames.
    # Then we have different code trying to access other actions,
    # so we have little choice than to import them here too, as
    # include('django.contrib.auth.urls') doesn't work due to login
    # override above.
    url(r'^{mount_point}accounts/login/$'.format(mount_point=settings.MOUNT_POINT),
        'django.contrib.auth.views.login', {'authentication_form': AuthenticationForm}, name='login'),
    url(r'^{mount_point}accounts/logout/$'.format(mount_point=settings.MOUNT_POINT),
        'django.contrib.auth.views.logout'),
    url(r'^{mount_point}password_change/done/$'.format(mount_point=settings.MOUNT_POINT),
        'django.contrib.auth.views.password_change_done', name='password_change_done'),
    url(r'^{mount_point}password_change/$'.format(mount_point=settings.MOUNT_POINT),
        'django.contrib.auth.views.password_change'),
    url(r'^{mount_point}password_reset/$'.format(mount_point=settings.MOUNT_POINT),
        'django.contrib.auth.views.password_reset', name='password_reset'),
    url(r'^{mount_point}password_reset/done/$'.format(mount_point=settings.MOUNT_POINT),
        'django.contrib.auth.views.password_reset_done'),
    url(r'^{mount_point}admin_password_reset/$'.format(mount_point=settings.MOUNT_POINT),
        'django.contrib.auth.views.password_reset', dict(is_admin_site=True)),
    url(r'^%sreset/(?P<uidb36>[0-9A-Za-z]{1,13})-(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$' % settings.MOUNT_POINT,
        'django.contrib.auth.views.password_reset_confirm'),
    url(r'^{mount_point}reset/done/$'.format(mount_point=settings.MOUNT_POINT),
        'django.contrib.auth.views.password_reset_complete'),

    url(r'^admin/jsi18n', 'django.views.i18n.javascript_catalog'),
    url(r'^{mount_point}admin/'.format(mount_point=settings.MOUNT_POINT),
        include(admin.site.urls)),
    url(r'^{mount_point}openid/'.format(mount_point=settings.MOUNT_POINT),
        include('django_openid_auth.urls')),
    url(r'^{mount_point}RPC2/?'.format(mount_point=settings.MOUNT_POINT),
        'linaro_django_xmlrpc.views.handler',
        name='lava.api_handler',
        kwargs={
            'mapper': loader.xmlrpc_mapper,
            'help_view': 'lava.api_help'}),
    url(r'^{mount_point}api/help/$'.format(mount_point=settings.MOUNT_POINT),
        'linaro_django_xmlrpc.views.help',
        name='lava.api_help',
        kwargs={
            'mapper': loader.xmlrpc_mapper}),
    url(r'^{mount_point}api/'.format(mount_point=settings.MOUNT_POINT),
        include(api_urls.token_urlpatterns)),
    # XXX: This is not needed but without it linaro-django-xmlrpc tests fail
    url(r'^{mount_point}api/'.format(mount_point=settings.MOUNT_POINT),
        include(api_urls.default_mapper_urlpatterns)),
    url(r'^{mount_point}utils/markitup/'.format(mount_point=settings.MOUNT_POINT),
        include('lava_markitup.urls')))


# Load URLs for extensions
loader.contribute_to_urlpatterns(urlpatterns, settings.MOUNT_POINT)
