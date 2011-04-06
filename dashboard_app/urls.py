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

from dashboard_app.views import (
    attachment_detail,
    bundle_stream_list,
    bundle_list,
    dashboard_xml_rpc_handler,
    restricted_view,
    test_result_detail,
    test_run_detail,
    test_run_hardware_context,
    test_run_list,
    test_run_software_context,
)

urlpatterns = patterns(
    '',
    url(r'^streams/$',
        bundle_stream_list,
        name='dashboard_app.bundle_stream_list'),
    url(r'^test-results/(?P<pk>[0-9]+)/$',
        test_result_detail,
        name='dashboard_app.views.test_result_detail'),
    url(r'^test-runs/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/$',
        test_run_detail,
        name='dashboard_app.views.test_run_detail'),
    url(r'^test-runs/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/software-context$',
        test_run_software_context,
        name='dashboard_app.views.test_run_software_context'),
    url(r'^test-runs/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/hardware-context$',
        test_run_hardware_context,
        name='dashboard_app.views.test_run_hardware_context'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/-]+)$',
        test_run_list,
        name='dashboard_app.test_run_list'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/-]+?)\+bundles$',
        bundle_list,
        name='dashboard_app.views.bundle_list'),
    url(r'^attachments/(?P<pk>[0-9]+)/$',
        attachment_detail,
        name='dashboard_app.views.attachment_detail'),
    url(r'^xml-rpc/',
        dashboard_xml_rpc_handler,
        name='dashboard_app.dashboard_xml_rpc_handler'),
    url(r'^restricted/$',
        restricted_view)
)
