# Copyright (c) 2010 Linaro
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
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
"""
from django.conf.urls.defaults import *

from dashboard_app.views import (
        bundle_stream_detail,
        bundle_stream_list,
        dashboard_xml_rpc_handler,
        )

urlpatterns = patterns('',
        url(r'^streams/$', bundle_stream_list,
            name='dashboard_app.bundle_stream_list'),
        url(r'^streams(?P<pathname>/[a-zA-Z0-9/-]+/)$', bundle_stream_detail,
            name='dashboard_app.bundle_stream_detail'),
        url(r'^xml-rpc/', dashboard_xml_rpc_handler,
            name='dashboard_app.dashboard_xml_rpc_handler'),
        )
