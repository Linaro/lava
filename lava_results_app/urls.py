# Copyright (C) 2015 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# This file is part of Lava Server.
#
# Lava Server is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Lava Server is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Lava Dashboard.  If not, see <http://www.gnu.org/licenses/>.

"""
URL mappings for the LAVA Results application
"""
from django.conf.urls import *
from lava_results_app.views import (
    index,
    metadata_export,
    suite,
    suite_csv_stream,
    suite_csv,
    suite_yaml,
    testcase,
    testjob,
    testjob_csv,
    testjob_yaml,
    testset,
)
from lava_results_app.views.query.views import (
    get_query_group_names,
    get_query_names,
    query_list,
    query_add,
    query_add_condition,
    query_add_group,
    query_copy,
    query_custom,
    query_delete,
    query_detail,
    query_display,
    query_edit,
    query_edit_condition,
    query_export,
    query_export_custom,
    query_group_list,
    query_refresh,
    query_remove_condition,
    query_omit_result,
    query_include_result,
    query_select_group,
    query_toggle_published,
)
from lava_results_app.views.chart.views import (
    get_chart_group_names,
    chart_list,
    chart_add,
    chart_add_group,
    chart_custom,
    chart_delete,
    chart_detail,
    chart_display,
    chart_edit,
    chart_group_list,
    chart_select_group,
    chart_toggle_published,
    chart_query_add,
    chart_query_edit,
    chart_query_remove,
    chart_query_order_update,
    chart_omit_result,
    settings_update
)

urlpatterns = [
    url(r'^$', index, name='lava_results'),
    url(r'^query$', query_list, name='lava.results.query_list'),
    url(r'^query/\+add$', query_add, name='lava.results.query_add'),
    url(r'^query/\+custom$', query_custom, name='lava.results.query_custom'),
    url(r'^query/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)$',
        query_display, name='lava.results.query_display'),
    url(r'^query/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+detail$',
        query_detail, name='lava.results.query_detail'),
    url(r'^query/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+edit$',
        query_edit, name='lava.results.query_edit'),
    url(r'^query/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+delete$',
        query_delete, name='lava.results.query_delete'),
    url(r'^query/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+export$',
        query_export, name='lava.results.query_export'),
    url(r'^query/\+export-custom$', query_export_custom, name='lava.results.query_export_custom'),
    url(r'^query/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+toggle-published$', query_toggle_published,
        name='lava.results.query_toggle_published'),
    url(r'^query/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+copy$', query_copy),
    url(r'^query/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+refresh$', query_refresh, name='lava.results.query_refresh'),
    url(r'^query/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+add-condition$', query_add_condition,
        name='lava.results.query_add_condition'),
    url(r'^query/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/\+remove-condition$', query_remove_condition,
        name='lava.results.query_remove_condition'),
    url(r'^query/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/\+edit-condition$', query_edit_condition,
        name='lava.results.query_edit_condition'),
    url(r'^query/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+add-group$', query_add_group, name='query_add_group'),
    url(r'^query/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/\+select-group$', query_select_group, name='query_select_group'),
    url(r'^query/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/\+omit-result$', query_omit_result, name='lava.results.query_omit_result'),
    url(r'^query/~(?P<username>[^/]+)/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/\+include-result$', query_include_result, name='lava.results.query_include_result'),
    url(r'^query/get-query-groups$', query_group_list, name='query_group_list'),
    url(r'^query/\+get-group-names$', get_query_group_names),
    url(r'^query/\+get-query-names$', get_query_names),
    url(r'^(?P<job>[0-9]+|[0-9]+.[0-9]+)$', testjob, name='lava.results.testjob'),
    url(r'^(?P<job>[0-9]+|[0-9]+.[0-9]+)/csv$', testjob_csv, name='lava.results.testjob_csv'),
    url(r'^(?P<job>[0-9]+|[0-9]+.[0-9]+)/yaml$', testjob_yaml, name='lava.results.testjob_yaml'),
    url(r'^(?P<job>[0-9]+|[0-9]+.[0-9]+)/metadata$',
        metadata_export, name='lava.results.job.metadata'),
    url(r'^(?P<job>[0-9]+|[0-9]+.[0-9]+)/(?P<pk>[-_a-zA-Z0-9.]+)$', suite, name='lava.results.suite'),
    url(r'^chart$', chart_list, name='lava.results.chart_list'),
    url(r'^chart/\+add$', chart_add, name='lava.results.chart_add'),
    url(r'^chart/\+custom$', chart_custom, name='lava.results.chart_custom'),
    url(r'^chart/(?P<name>[a-zA-Z0-9-_]+)$', chart_display,
        name='lava.results.chart_display'),
    url(r'^chart/(?P<name>[a-zA-Z0-9-_]+)/\+detail$', chart_detail,
        name='lava.results.chart_detail'),
    url(r'^chart/(?P<name>[a-zA-Z0-9-_]+)/\+edit$', chart_edit,
        name='lava.results.chart_edit'),
    url(r'^chart/(?P<name>[a-zA-Z0-9-_]+)/\+delete$', chart_delete,
        name='lava.results.chart_delete'),
    url(r'^chart/(?P<name>[a-zA-Z0-9-_]+)/\+toggle-published$',
        chart_toggle_published, name='lava.results.chart_toggle_published'),
    url(r'^chart/(?P<name>[a-zA-Z0-9-_]+)/\+chart-query-add$', chart_query_add,
        name='lava.results.chart_query_add'),
    url(r'^chart/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/\+chart-query-remove$',
        chart_query_remove, name='lava.results.chart_query_remove'),
    url(r'^chart/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/\+chart-query-edit$',
        chart_query_edit, name='lava.results.chart_query_edit'),
    url(r'^chart/(?P<name>[a-zA-Z0-9-_]+)/\+add-group$', chart_add_group,
        name='chart_add_group'),
    url(r'^chart/(?P<name>[a-zA-Z0-9-_]+)/\+select-group$', chart_select_group,
        name='chart_select_group'),
    url(r'^chart/get-chart-groups$', chart_group_list,
        name='chart_group_list'),
    url(r'^chart/\+get-group-names$', get_chart_group_names),
    url(r'^chart/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/\+settings-update$', settings_update, name='chart_settings_update'),
    url(r'^chart/(?P<name>[a-zA-Z0-9-_]+)/\+chart-query-order-update$', chart_query_order_update, name='chart_query_order_update'),
    url(r'^chart/(?P<name>[a-zA-Z0-9-_]+)/(?P<id>\d+)/(?P<result_id>\d+)/\+omit-result$', chart_omit_result, name='lava.results.chart_omit_result'),
    url(r'^(?P<job>[0-9]+|[0-9]+.[0-9]+)/(?P<pk>[-_a-zA-Z0-9.]+)/(?P<ts>[-_a-zA-Z0-9.]+)/(?P<case>[-_a-zA-Z0-9.+]+)$', testset, name='lava.results.testset'),
    url(r'^(?P<job>[0-9]+|[0-9]+.[0-9]+)/(?P<pk>[-_a-zA-Z0-9.]+)/csv$',
        suite_csv, name='lava.results.suite_csv'),
    url(r'^(?P<job>[0-9]+|[0-9]+.[0-9]+)/(?P<pk>[-_a-zA-Z0-9.]+)/stream/csv$',
        suite_csv_stream, name='lava.results.suite_csv_stream'),
    url(r'^(?P<job>[0-9]+|[0-9]+.[0-9]+)/(?P<pk>[-_a-zA-Z0-9.]+)/yaml$',
        suite_yaml, name='lava.results.suite_yaml'),
    url(r'^(?P<job>[0-9]+|[0-9]+.[0-9]+)/(?P<pk>[-_a-zA-Z0-9.]+)/(?P<case>[-_a-zA-Z0-9.\(\)+]+)$',
        testcase, name='lava.results.testcase')
]
