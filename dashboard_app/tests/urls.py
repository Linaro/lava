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
    url(r'^auth-test/', auth_test))
