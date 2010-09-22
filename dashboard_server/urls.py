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
from django.contrib import databrowse
from django.views.generic.simple import direct_to_template

import dashboard_app.urls

from dashboard_app.models import (
    Attachment,
    Bundle,
    BundleStream,
    HardwareDevice,
    NamedAttribute,
    SoftwarePackage,
    Test,
    TestCase,
    TestResult,
    TestRun,
)

# Register our models with data browser
databrowse.site.register(Attachment)
databrowse.site.register(Bundle)
databrowse.site.register(BundleStream)
databrowse.site.register(HardwareDevice)
databrowse.site.register(NamedAttribute)
databrowse.site.register(SoftwarePackage)
databrowse.site.register(Test)
databrowse.site.register(TestCase)
databrowse.site.register(TestResult)
databrowse.site.register(TestRun)

# Enable admin stuff
admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', direct_to_template,
        name='home',
        kwargs={'template': 'index.html'}),
    url(r'^about-alpha/', direct_to_template,
        name='about-alpha',
        kwargs={'template': 'about_alpha.html'}),
    url(r'^databrowse/(.*)', databrowse.site.root),
    (r'^admin/', include(admin.site.urls)),
    (r'', include(dashboard_app.urls)),
    )

if not settings.CONFIGURED:
    # This is only used when we cannot count on static media files being
    # served by some real web server. WARNING: this is not secure and
    # should _never_ be used in production environments.
    # See:
    # http://docs.djangoproject.com/en/1.2/howto/static-files/#the-big-fat-disclaimer)
    urlpatterns += patterns('',
            (r'^site_media/(?P<path>.*)$', 'django.views.static.serve', {
                'document_root': settings.MEDIA_ROOT,
                'show_indexes': True}))

