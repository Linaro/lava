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
from django.conf.urls.defaults import * 
from django.contrib import admin
from django.views.generic.simple import direct_to_template
from staticfiles.urls import staticfiles_urlpatterns

from lava_server.extension import loader


# Enable admin stuff
admin.autodiscover()


# Root URL patterns
urlpatterns = patterns(
    '',
    url(r'^' + settings.APP_URL_PREFIX + r'$', direct_to_template,
        name='lava.home', kwargs={'template': 'index.html'}),
    url(r'^' + settings.APP_URL_PREFIX + r'version/$', direct_to_template,
        name='lava.version_details', kwargs={'template': 'version_details.html'}),
    url(r'^' + settings.APP_URL_PREFIX + r'accounts/', include('django.contrib.auth.urls')),
    url(r'^' + settings.APP_URL_PREFIX + r'admin/', include(admin.site.urls)),
    url(r'^' + settings.APP_URL_PREFIX + r'openid/', include('django_openid_auth.urls')),
)


# Enable static files serving for development server
# NOTE: This can be removed in django 1.3
if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()


# Load URLs for extensions
loader.contribute_to_urlpatterns(urlpatterns)
