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
    url(r'^$', 'index'),
    url(r'^data-views/$', 'data_view_list'),
    url(r'^data-views/(?P<name>[a-zA-Z0-9-_]+)/$', 'data_view_detail'),
    url(r'^reports/$', 'report_list'),
    url(r'^reports/(?P<name>[a-zA-Z0-9-_]+)/$', 'report_detail'),
    url(r'^filters/$', 'filters.views.filters_list'),
    url(r'^filters/filters_names_json$', 'filters.views.filter_name_list_json', name='filter_name_list_json'),
    url(r'^filters/\+add$', 'filters.views.filter_add'),
    url(r'^filters/\+add-cases-for-test-json$', 'filters.views.filter_add_cases_for_test_json'),
    url(r'^filters/\+get-tests-json$', 'filters.views.get_tests_json'),
    url(r'^filters/\+get-test-cases-json$', 'filters.views.get_test_cases_json'),
    url(r'^filters/\+attribute-name-completion-json$', 'filters.views.filter_attr_name_completion_json'),
    url(r'^filters/\+attribute-value-completion-json$', 'filters.views.filter_attr_value_completion_json'),
    url(r'^filters/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)$', 'filters.views.filter_detail'),
    url(r'^filters/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+edit$', 'filters.views.filter_edit'),
    url(r'^filters/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+subscribe$', 'filters.views.filter_subscribe'),
    url(r'^filters/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+delete$', 'filters.views.filter_delete'),
    url(r'^filters/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+compare/(?P<tag1>[a-zA-Z0-9-_: .]+)/(?P<tag2>[a-zA-Z0-9-_: .]+)$', 'filters.views.compare_matches'),
    url(r'^streams/$', 'bundle_stream_list'),
    url(r'^streams/mybundlestreams$', 'mybundlestreams'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/$', 'bundle_list'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/+export$', 'bundle_list_export'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/$', 'bundle_detail'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/+export$', 'bundle_export'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/json$', 'bundle_json'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/$', 'test_run_detail'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/+export$', 'test_run_export'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/result/(?P<relative_index>[0-9]+)/$', 'test_result_detail'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/result/(?P<relative_index>[0-9]+)/\+update-comments$', 'test_result_update_comments'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/hardware-context/$', 'test_run_hardware_context'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/software-context/$', 'test_run_software_context'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)test-runs/$', 'test_run_list'),
    url(r'^attachment/(?P<pk>[0-9]+)/download$', 'attachment_download'),
    url(r'^attachment/(?P<pk>[0-9]+)/view$', 'attachment_view'),
    url(r'^permalink/test-run/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/$', 'redirect_to_test_run'),
    url(r'^permalink/test-run/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/(?P<trailing>.*)$', 'redirect_to_test_run'),
    url(r'^permalink/test-result/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/(?P<relative_index>[0-9]+)/$', 'redirect_to_test_result'),
    url(r'^permalink/test-result/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/(?P<relative_index>[0-9]+)/(?P<trailing>.*)$', 'redirect_to_test_result'),
    url(r'^permalink/bundle/(?P<content_sha1>[0-9a-z]+)/$', 'redirect_to_bundle'),
    url(r'^permalink/bundle/(?P<content_sha1>[0-9a-z]+)/(?P<trailing>.*)$', 'redirect_to_bundle'),
    url(r'^image-reports/$', 'images.image_report_list'),
    url(r'^image-charts/$', 'image_reports.views.image_report_list',
        name='image_report_list'),
    url(r'^image-charts/get-report-groups$', 'image_reports.views.image_report_group_list', name='image_report_group_list'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)$', 'image_reports.views.image_report_display'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+detail$', 'image_reports.views.image_report_detail', name='image_report_detail'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+add-group$', 'image_reports.views.image_report_add_group', name='image_report_add_group'),
    url(r'^image-charts/\+add$', 'image_reports.views.image_report_add'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+edit$', 'image_reports.views.image_report_edit'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+delete$', 'image_reports.views.image_report_delete'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+publish$', 'image_reports.views.image_report_publish'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+unpublish$', 'image_reports.views.image_report_unpublish'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>[a-zA-Z0-9-_]+)$', 'image_reports.views.image_chart_detail'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+add$', 'image_reports.views.image_chart_add'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>[a-zA-Z0-9-_]+)/\+edit$', 'image_reports.views.image_chart_edit'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>[a-zA-Z0-9-_]+)/\+delete$', 'image_reports.views.image_chart_delete'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>[a-zA-Z0-9-_]+)/\+settings-update$', 'image_reports.views.image_chart_settings_update'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>[a-zA-Z0-9-_]+)/\+export$', 'image_reports.views.image_chart_export'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>[a-zA-Z0-9-_]+)/\+add-filter$', 'image_reports.views.image_chart_filter_add'),
    url(r'^image-chart-filter/(?P<id>[a-zA-Z0-9-_]+)$', 'image_reports.views.image_chart_filter_edit'),
    url(r'^image-chart-filter/(?P<id>[a-zA-Z0-9-_]+)/\+delete$', 'image_reports.views.image_chart_filter_delete'),
    url(r'^pmqa$', 'pmqa.pmqa_view'),
    url(r'^pmqa(?P<pathname>/[a-zA-Z0-9/._-]+/)(?P<device_type>[a-zA-Z0-9-_]+)$', 'pmqa.pmqa_filter_view'),
    url(r'^pmqa(?P<pathname>/[a-zA-Z0-9/._-]+/)(?P<device_type>[a-zA-Z0-9-_]+)/json$', 'pmqa.pmqa_filter_view_json'),
    url(r'^pmqa(?P<pathname>/[a-zA-Z0-9/._-]+/)(?P<device_type>[a-zA-Z0-9-_]+)/\+compare/(?P<build1>[0-9]+)/(?P<build2>[0-9]+)$', 'pmqa.compare_pmqa_results'),
    url(r'^image-reports/(?P<name>[A-Za-z0-9_-]+)$', 'images.image_report_detail'),
    url(r'^api/link-bug-to-testrun', 'images.link_bug_to_testrun'),
    url(r'^api/unlink-bug-and-testrun', 'images.unlink_bug_and_testrun'),
    url(r'^test-definition/add_test_definition', 'add_test_definition'),
    url(r'^test-definition/$', 'test_definition'),
)
