# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Lava Dashboard.
#
# Lava Dashboard is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Lava Dashboard is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Lava Dashboard.  If not, see <http://www.gnu.org/licenses/>.

"""
URL mappings for the Dashboard application
"""
from django.conf.urls import *

urlpatterns = patterns(
    'dashboard_app.views',
    url(r'^$', 'index', name='lava.dashboard'),
    url(r'^filters/$', 'filters.views.filters_list', name='lava.dashboard.filters_list'),
    url(r'^filters/filters_names_json$', 'filters.views.filter_name_list_json', name='filter_name_list_json'),
    url(r'^filters/\+add$', 'filters.views.filter_add'),
    url(r'^filters/\+add-cases-for-test-json$', 'filters.views.filter_add_cases_for_test_json'),
    url(r'^filters/\+get-tests-json$', 'filters.views.get_tests_json'),
    url(r'^filters/\+get-test-cases-json$', 'filters.views.get_test_cases_json'),
    url(r'^filters/\+attribute-name-completion-json$', 'filters.views.filter_attr_name_completion_json'),
    url(r'^filters/\+attribute-value-completion-json$', 'filters.views.filter_attr_value_completion_json'),
    url(r'^filters/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)$', 'filters.views.filter_detail'),
    url(r'^filters/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+edit$', 'filters.views.filter_edit'),
    url(r'^filters/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+copy$', 'filters.views.filter_copy'),
    url(r'^filters/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+subscribe$', 'filters.views.filter_subscribe'),
    url(r'^filters/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+delete$', 'filters.views.filter_delete'),
    url(r'^filters/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+compare/(?P<tag1>[a-zA-Z0-9-_: .]+)/(?P<tag2>[a-zA-Z0-9-_: .]+)$', 'filters.views.compare_matches'),
    url(r'^my-subscriptions$', 'my_subscriptions', name='lava.dashboard.my_subscriptions'),
    url(r'^streams/$', 'bundle_stream_list', name="lava.dashboard.bundle.list"),
    url(r'^streams/mybundlestreams$', 'mybundlestreams'),
    url(r'^streams/bundlestreams-json$', 'bundlestreams_json'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/$', 'bundle_list'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/+export$', 'bundle_list_export'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/$', 'bundle_detail'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/+export$', 'bundle_export'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/json$', 'bundle_json'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/$', 'test_run_detail'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/+export$', 'test_run_export'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/\+update-testrun-attribute$', 'test_run_update_attribute'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/\+remove-testrun-attribute$', 'test_run_remove_attribute'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/result/(?P<relative_index>[0-9]+)/$', 'test_result_detail'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/result/(?P<relative_index>[0-9]+)/\+update-comments$', 'test_result_update_comments'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/result/(?P<relative_index>[0-9]+)/\+update-result-attribute$', 'test_result_update_attribute'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/result/(?P<relative_index>[0-9]+)/\+remove-result-attribute$', 'test_result_remove_attribute'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/hardware-context/$', 'test_run_hardware_context'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/software-context/$', 'test_run_software_context'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)test-runs/$', 'test_run_list'),
    url(r'^attachment/(?P<pk>\d+)/download$', 'attachment_download'),
    url(r'^attachment/(?P<pk>\d+)/view$', 'attachment_view'),
    url(r'^permalink/test-run/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/$', 'redirect_to_test_run'),
    url(r'^permalink/test-run/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/(?P<trailing>.*)$', 'redirect_to_test_run'),
    url(r'^permalink/test-result/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/(?P<relative_index>\d+)/$', 'redirect_to_test_result'),
    url(r'^permalink/test-result/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/(?P<relative_index>\d+)/(?P<trailing>.*)$', 'redirect_to_test_result'),
    url(r'^permalink/bundle/(?P<content_sha1>[0-9a-z]+)/$', 'redirect_to_bundle'),
    url(r'^permalink/bundle/(?P<content_sha1>[0-9a-z]+)/(?P<trailing>.*)$', 'redirect_to_bundle'),
    url(r'^image-reports/$', 'images.image_report_list', name='lava.dashboard.image.report_list'),
    url(r'^image-reports/(?P<name>[A-Za-z0-9_-]+)$', 'images.image_report_detail'),
    url(r'^image-charts/$', 'image_reports.views.image_report_list',
        name='lava.dashboard.image_report.report_list'),
    url(r'^image-charts/get-report-groups$', 'image_reports.views.image_report_group_list', name='image_report_group_list'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)$', 'image_reports.views.image_report_display'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+detail$', 'image_reports.views.image_report_detail', name='image_report_detail'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+add-group$', 'image_reports.views.image_report_add_group', name='image_report_add_group'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+select-group$', 'image_reports.views.image_report_select_group', name='image_report_select_group'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+order-update$', 'image_reports.views.image_report_order_update', name='image_report_order_update'),
    url(r'^image-charts/\+add$', 'image_reports.views.image_report_add'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+edit$', 'image_reports.views.image_report_edit'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+delete$', 'image_reports.views.image_report_delete'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+publish$', 'image_reports.views.image_report_publish'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+unpublish$', 'image_reports.views.image_report_unpublish'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)$', 'image_reports.views.image_chart_detail'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+add$', 'image_reports.views.image_chart_add'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/\+edit$', 'image_reports.views.image_chart_edit'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/\+delete$', 'image_reports.views.image_chart_delete'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/\+settings-update$', 'image_reports.views.image_chart_settings_update'),
    url(r'^image-charts/\+filter-type-check$', 'image_reports.views.image_chart_filter_type_check'),
    url(r'^image-charts/\+get-chart-test$', 'image_reports.views.get_chart_test_data'),
    url(r'^image-charts/\+get-group-names$', 'image_reports.views.get_group_names'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/\+export$', 'image_reports.views.image_chart_export'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/\+add-filter$', 'image_reports.views.image_chart_filter_add'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/(?P<slug>\d+)$', 'image_reports.views.image_chart_filter_detail'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/(?P<slug>\d+)/\+edit$', 'image_reports.views.image_chart_filter_edit'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/(?P<slug>\d+)/\+delete$', 'image_reports.views.image_chart_filter_delete'),
    url(r'^api/link-bug-to-testrun', 'link_bug_to_testrun'),
    url(r'^api/unlink-bug-and-testrun', 'unlink_bug_and_testrun'),
    url(r'^api/link-bug-to-testresult', 'link_bug_to_testresult'),
    url(r'^api/unlink-bug-and-testresult', 'unlink_bug_and_testresult'),
)
