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

https://docs.djangoproject.com/en/1.8/topics/http/urls/#naming-url-patterns
https://docs.djangoproject.com/en/1.8/releases/1.8/#passing-a-dotted-path-to-reverse-and-url

Avoid letting the name attribute of a url look like a python path - use underscore
instead of period. The name is just a label, using it as a path is deprecated and
support will be removed in Django1.10. Equally, always provide a name if the URL
needs to be reversed elsewhere in the code, e.g. the view. (Best practice is to
use a name for all new urls, even if not yet used elsewhere.)
"""
from django.conf.urls import *
from dashboard_app.views import (
    attachment_download,
    attachment_view,
    bundle_detail,
    bundle_export,
    bundle_json,
    bundle_list,
    bundle_list_export,
    bundle_stream_list,
    bundlestreams_json,
    index,
    mybundlestreams,
    my_subscriptions,
    test_run_detail,
    test_run_export,
    test_run_update_attribute,
    test_result_update_comments,
    test_run_remove_attribute,
    test_result_detail,
    test_result_update_units,
    test_result_update_attribute,
    test_result_remove_attribute,
    test_run_hardware_context,
    test_run_software_context,
    test_run_list,
    redirect_to_bundle,
    redirect_to_test_run,
    redirect_to_test_result,
)

from dashboard_app.views.filters.views import (
    compare_matches,
    filter_add,
    filter_add_cases_for_test_json,
    filter_attr_name_completion_json,
    filter_attr_value_completion_json,
    filter_copy,
    filter_delete,
    filter_detail,
    filter_edit,
    filters_list,
    filter_name_list_json,
    filter_subscribe,
    get_tests_json,
    get_test_cases_json,
)

from dashboard_app.views.images import (
    image_report_detail as images_report_detail,
    image_report_list as images_report_list,
)

from dashboard_app.views.image_reports.views import (
    get_chart_test_data,
    get_group_names,
    image_chart_add,
    image_chart_detail,
    image_chart_delete,
    image_chart_edit,
    image_chart_export,
    image_chart_settings_update,
    image_chart_filter_add,
    image_chart_filter_detail,
    image_chart_filter_delete,
    image_chart_filter_edit,
    image_chart_filter_type_check,
    image_report_detail,
    image_report_list,
    image_report_display,
    image_report_detail,
    image_report_add_group,
    image_report_select_group,
    image_report_order_update,
    image_report_edit,
    image_report_add,
    image_report_group_list,
    image_report_delete,
    image_report_publish,
    image_report_unpublish,
)
from dashboard_app.views import (
    link_bug_to_testrun,
    unlink_bug_and_testrun,
    link_bug_to_testresult,
    unlink_bug_and_testresult
)


urlpatterns = [
    url(r'^$', index, name='lava_dashboard'),
    url(r'^filters/$', filters_list, name='lava_dashboard_filters_list'),
    url(r'^filters/filters_names_json$', filter_name_list_json, name='filter_name_list_json'),
    url(r'^filters/\+add$', filter_add, name='dashboard_app.views.filters.views.filter_add'),
    url(r'^filters/\+add-cases-for-test-json$', filter_add_cases_for_test_json,
        name='dashboard_app.views.filters.views.filter_add_cases_for_test_json'),
    url(r'^filters/\+get-tests-json$', get_tests_json),
    url(r'^filters/\+get-test-cases-json$', get_test_cases_json),
    url(r'^filters/\+attribute-name-completion-json$', filter_attr_name_completion_json,
        name='dashboard_app.views.filters.views.filter_attr_name_completion_json'),
    url(r'^filters/\+attribute-value-completion-json$', filter_attr_value_completion_json,
        name='dashboard_app.views.filters.views.filter_attr_value_completion_json'),
    url(r'^filters/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)$', filter_detail,
        name='dashboard_app.views.filters.views.filter_detail'),
    url(r'^filters/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+edit$', filter_edit,
        name='dashboard_app.views.filters.views.filter_edit'),
    url(r'^filters/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+copy$', filter_copy,
        name='dashboard_app.views.filters.views.filter_copy'),
    url(r'^filters/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+subscribe$', filter_subscribe,
        name='dashboard_app.views.filters.views.filter_subscribe'),
    url(r'^filters/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+delete$', filter_delete,
        name='dashboard_app.views.filters.views.filter_delete'),
    url(r'^filters/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+compare/(?P<tag1>[a-zA-Z0-9-_: .+]+)/(?P<tag2>[a-zA-Z0-9-_: .+]+)$',
        compare_matches),
    url(r'^my-subscriptions$', my_subscriptions, name='lava_dashboard_my_subscriptions'),
    url(r'^streams/$', bundle_stream_list, name="lava_dashboard_bundle_stream_list"),
    url(r'^streams/mybundlestreams$', mybundlestreams, name='lava_dashboard_mybundlestreams'),
    url(r'^streams/bundlestreams-json$', bundlestreams_json),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/$', bundle_list, name='lava_dashboard_bundle_list'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/+export$', bundle_list_export,
        name='lava_dashboard_bundle_list_export'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/$', bundle_detail,
        name='lava_dashboard_bundle_detail'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/+export$', bundle_export,
        name='lava_dashboard_bundle_export'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/json$', bundle_json),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/$',
        test_run_detail, name='lava_dashboard_test_run_detail'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/+export$',
        test_run_export, name='lava_dashboard_test_run_export'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/\+update-testrun-attribute$',
        test_run_update_attribute),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/\+remove-testrun-attribute$',
        test_run_remove_attribute),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/result/(?P<relative_index>[0-9]+)/$',
        test_result_detail, name='lava_dashboard_test_result_detail'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/result/(?P<relative_index>[0-9]+)/\+update-comments$',
        test_result_update_comments),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/result/(?P<relative_index>[0-9]+)/\+update-units$',
        test_result_update_units),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/result/(?P<relative_index>[0-9]+)/\+update-result-attribute$',
        test_result_update_attribute),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/result/(?P<relative_index>[0-9]+)/\+remove-result-attribute$',
        test_result_remove_attribute),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/hardware-context/$',
        test_run_hardware_context, name='lava_dashboard_test_run_hardware_context'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)bundles/(?P<content_sha1>[0-9a-z]+)/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/software-context/$',
        test_run_software_context, name='lava_dashboard_test_run_software_context'),
    url(r'^streams(?P<pathname>/[a-zA-Z0-9/._-]+)test-runs/$', test_run_list, name='lava_dashboard_test_run_list'),
    url(r'^attachment/(?P<pk>\d+)/download$', attachment_download,
        name='dashboard_app.views.attachment_download'),
    url(r'^attachment/(?P<pk>\d+)/view$', attachment_view,
        name='dashboard_app.views.attachment_view'),
    url(r'^permalink/test-run/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/$', redirect_to_test_run,
        name='lava_dashboard_redirect_to_test_run'),
    url(r'^permalink/test-run/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/(?P<trailing>.*)$', redirect_to_test_run,
        name='lava_dashboard_redirect_to_test_run_trailing'),
    url(r'^permalink/test-result/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/(?P<relative_index>\d+)/$',
        redirect_to_test_result, name='lava_dashboard_redirect_to_test_result'),
    url(r'^permalink/test-result/(?P<analyzer_assigned_uuid>[a-zA-Z0-9-]+)/(?P<relative_index>\d+)/(?P<trailing>.*)$',
        redirect_to_test_result, name='lava_dashboard_redirect_to_test_result_trailing'),
    url(r'^permalink/bundle/(?P<content_sha1>[0-9a-z]+)/$', redirect_to_bundle,
        name='lava_dashboard_redirect_to_bundle'),
    url(r'^permalink/bundle/(?P<content_sha1>[0-9a-z]+)/(?P<trailing>.*)$', redirect_to_bundle,
        name='lava_dashboard_redirect_to_bundle_trailing'),
    url(r'^image-reports/$', images_report_list, name='lava_dashboard_image_report_list'),
    url(r'^image-reports/(?P<name>[A-Za-z0-9_-]+)$', images_report_detail,
        name='dashboard_app.views.images.image_report_detail'),
    url(r'^image-charts/$', image_report_list,
        name='lava_dashboard_image_report_report_list'),
    url(r'^image-charts/get-report-groups$', image_report_group_list,
        name='image_report_group_list'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)$', image_report_display,
        name='dashboard_app.views.image_reports.views.image_report_display'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+detail$', image_report_detail,
        name='image_report_detail'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+add-group$', image_report_add_group,
        name='image_report_add_group'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+select-group$', image_report_select_group,
        name='image_report_select_group'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+order-update$', image_report_order_update,
        name='image_report_order_update'),
    url(r'^image-charts/\+add$', image_report_add,
        name='dashboard_app.views.image_reports.views.image_report_add'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+edit$', image_report_edit),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+delete$', image_report_delete),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+publish$', image_report_publish),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+unpublish$', image_report_unpublish),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)$', image_chart_detail,
        name='dashboard_app.views.image_reports.views.image_chart_detail'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/\+add$', image_chart_add,
        name='dashboard_app.views.image_reports.views.image_chart_add'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/\+edit$', image_chart_edit),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/\+delete$', image_chart_delete),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/\+settings-update$', image_chart_settings_update),
    url(r'^image-charts/\+filter-type-check$', image_chart_filter_type_check),
    url(r'^image-charts/\+get-chart-test$', get_chart_test_data),
    url(r'^image-charts/\+get-group-names$', get_group_names,
        name='dashboard_app.views.image_reports.views.get_group_names'),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/\+export$', image_chart_export),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/\+add-filter$', image_chart_filter_add),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/(?P<slug>\d+)$', image_chart_filter_detail),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/(?P<slug>\d+)/\+edit$', image_chart_filter_edit),
    url(r'^image-charts/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/(?P<slug>\d+)/\+delete$', image_chart_filter_delete),
    url(r'^api/link-bug-to-testrun', link_bug_to_testrun, name='lava_dashboard_link_bug_to_testrun'),
    url(r'^api/unlink-bug-and-testrun', unlink_bug_and_testrun, name='lava_dashboard_unlink_bug_and_testrun'),
    url(r'^api/link-bug-to-testresult', link_bug_to_testresult,
        name='lava_dashboard_link_bug_to_testresult'),
    url(r'^api/unlink-bug-and-testresult', unlink_bug_and_testresult,
        name='lava_dashboard_unlink_bug_and_testresult'),
]
