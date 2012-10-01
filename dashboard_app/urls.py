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

from dashboard_app.xmlrpc import legacy_mapper
import linaro_django_xmlrpc.views

urlpatterns = patterns(
    'dashboard_app.views',
    url(r'^$', 'index'),
    url(r'^ajax/bundle-viewer/(?P<pk>[0-9]+)/$', 'ajax_bundle_viewer'),
    url(r'^ajax/attachment-viewer/(?P<pk>[0-9]+)/$', 'ajax_attachment_viewer'),
    url(r'^data-views/$', 'data_view_list'),
    url(r'^data-views/(?P<name>[a-zA-Z0-9-_]+)/$', 'data_view_detail'),
    url(r'^reports/$', 'report_list'),
    url(r'^reports/(?P<name>[a-zA-Z0-9-_]+)/$', 'report_detail'),
    url(r'^tests/$', 'test_list'),
    url(r'^tests/(?P<test_id>[^/]+)/$', 'test_detail'),
    url(r'^filters/$', 'filters.views.filters_list'),
    url(r'^filters/\+add$', 'filters.views.filter_add'),
    url(r'^filters/\+add-preview-json$', 'filters.views.filter_preview_json'),
    url(r'^filters/\+add-cases-for-test-json$', 'filters.views.filter_add_cases_for_test_json'),
    url(r'^filters/\+attribute-name-completion-json$', 'filters.views.filter_attr_name_completion_json'),
    url(r'^filters/\+attribute-value-completion-json$', 'filters.views.filter_attr_value_completion_json'),
    url(r'^filters/~(?P<username>[a-zA-Z0-9-_]+)/(?P<name>[a-zA-Z0-9-_]+)$', 'filters.views.filter_detail'),
    url(r'^filters/~(?P<username>[a-zA-Z0-9-_]+)/(?P<name>[a-zA-Z0-9-_]+)/json$', 'filters.views.filter_json'),
    url(r'^filters/~(?P<username>[a-zA-Z0-9-_]+)/(?P<name>[a-zA-Z0-9-_]+)/\+edit$', 'filters.views.filter_edit'),
    url(r'^filters/~(?P<username>[a-zA-Z0-9-_]+)/(?P<name>[a-zA-Z0-9-_]+)/\+subscribe$', 'filters.views.filter_subscribe'),
    url(r'^filters/~(?P<username>[a-zA-Z0-9-_]+)/(?P<name>[a-zA-Z0-9-_]+)/\+delete$', 'filters.views.filter_delete'),
    url(r'^xml-rpc/$', linaro_django_xmlrpc.views.handler, 
        name='dashboard_app.views.dashboard_xml_rpc_handler',
        kwargs={
            'mapper': legacy_mapper,
            'help_view': 'dashboard_app.views.dashboard_xml_rpc_help'}),
    url(r'^xml-rpc/help/$', linaro_django_xmlrpc.views.help,
        name='dashboard_app.views.dashboard_xml_rpc_help',
        kwargs={
            'mapper': legacy_mapper,
            'template_name': 'dashboard_app/api.html'}),
    url(r'^streams/$', 'bundle_stream_list'),
    url(r'^streams/json$', 'bundle_stream_list_json'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/$', 'bundle_list'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/json$', 'bundle_list_table_json'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/$', 'bundle_detail'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/json$', 'bundle_json'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/$', 'test_run_detail'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/json$', 'test_run_detail_test_json'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/attachments$', 'attachment_list'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/attachments/(?P<pk>[0-9]+)/$', 'attachment_detail'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/result/(?P<relative_index>[0-9]+)/$', 'test_result_detail'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/hardware-context/$', 'test_run_hardware_context'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/software-context/$', 'test_run_software_context'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)test-runs/$', 'test_run_list'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)test-runs/json$', 'test_run_list_json'),
    url(r'^permalink/test-run/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/$', 'redirect_to_test_run'),
    url(r'^permalink/test-run/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/(?P<trailing>.*)$', 'redirect_to_test_run'),
    url(r'^permalink/test-result/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/(?P<relative_index>[0-9]+)/$', 'redirect_to_test_result'),
    url(r'^permalink/test-result/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/(?P<relative_index>[0-9]+)/(?P<trailing>.*)$', 'redirect_to_test_result'),
    url(r'^permalink/bundle/(?P<content_sha1>[0-9a-z]+)/$', 'redirect_to_bundle'),
    url(r'^permalink/bundle/(?P<content_sha1>[0-9a-z]+)/(?P<trailing>.*)$', 'redirect_to_bundle'),
    url(r'^efforts/$', 'testing_effort_list'),
    url(r'^efforts/(?P<pk>[0-9]+)/$', 'testing_effort_detail'),
    url(r'^efforts/(?P<pk>[0-9]+)/update/$', 'testing_effort_update'),
    url(r'^efforts/(?P<project_identifier>[a-z0-9-]+)/\+new/$', 'testing_effort_create'),
    url(r'^image-reports/$', 'images.image_report_list'),
    url(r'^image-reports/(?P<name>[A-Za-z0-9_-]+)$', 'images.image_report_detail'),
    url(r'^api/link-bug-to-testrun', 'images.link_bug_to_testrun'),
    url(r'^api/unlink-bug-and-testrun', 'images.unlink_bug_and_testrun'),
)
