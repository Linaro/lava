# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

from django.conf import settings
from django.conf.urls.defaults import *
from django.contrib import admin
from django.views.generic.simple import direct_to_template

import dashboard_app.urls

from dashboard_app.models import (
    Attachment,
    Bundle,
    BundleDeserializationError,
    BundleStream,
    HardwareDevice,
    NamedAttribute,
    SoftwarePackage,
    Test,
    TestCase,
    TestResult,
    TestRun,
)
from dashboard_app.views import dashboard_xml_rpc_handler

# Enable admin stuff
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', direct_to_template,
        name='home',
        kwargs={'template': 'index.html'}),
    url(r'^about/$', direct_to_template,
        name='about',
        kwargs={'template': 'about.html'}),
    url(r'xml-rpc/', dashboard_xml_rpc_handler,
        name='xml-rpc'),
    url(r'^dashboard/', include('dashboard_app.urls')),
    url(r'^reports/', include('django_reports.urls')),
    url(r'accounts/', include('django.contrib.auth.urls')),
    (r'^admin/', include(admin.site.urls)),
    (r'^openid/', include('django_openid_auth.urls')),
    )

if settings.SERVE_ASSETS_FROM_DJANGO:
    urlpatterns += patterns('',
            (r'^site_media/(?P<path>.*)$', 'django.views.static.serve', {
                'document_root': settings.MEDIA_ROOT,
                'show_indexes': True}))

