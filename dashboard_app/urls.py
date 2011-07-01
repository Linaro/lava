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
"""
from django.conf.urls.defaults import *


urlpatterns = patterns(
    'dashboard_app.views',
    url(r'^streams/$', 'bundle_stream_list'),
    url(r'^test-results/(?P<pk>[0-9]+)/$', 'test_result_detail'),
    url(r'^test-runs/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/$', 'test_run_detail'),
    url(r'^test-runs/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/software-context$', 'test_run_software_context'),
    url(r'^test-runs/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/hardware-context$', 'test_run_hardware_context'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/_-]+)$', 'test_run_list'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/_-]+?)\+bundles$', 'bundle_list'),
    url(r'^attachments/(?P<pk>[0-9]+)/$', 'attachment_detail'),
    url(r'^xml-rpc/', 'dashboard_xml_rpc_handler'),
    url(r'^data-views/$', 'data_view_list'),
    url(r'^data-views/(?P<name>[a-zA-Z0-9-_]+)/$', 'data_view_detail'),
    url(r'^reports/$', 'report_list'),
    url(r'^reports/(?P<name>[a-zA-Z0-9-_]+)/$', 'report_detail'),
)
