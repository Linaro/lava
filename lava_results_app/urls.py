# Copyright (C) 2015-2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""
URL mappings for the LAVA Results application
"""
from django.urls import path, register_converter

from lava_common.converters import JobIdConverter
from lava_results_app.views import (
    index,
    suite,
    suite_csv,
    suite_csv_stream,
    suite_testcase_count,
    suite_yaml,
    testcase,
    testcase_yaml,
    testjob,
    testjob_csv,
    testjob_yaml,
    testjob_yaml_summary,
    testset,
)
from lava_results_app.views.chart.views import (
    chart_add,
    chart_add_group,
    chart_custom,
    chart_delete,
    chart_detail,
    chart_display,
    chart_edit,
    chart_group_list,
    chart_list,
    chart_omit_result,
    chart_query_add,
    chart_query_edit,
    chart_query_order_update,
    chart_query_remove,
    chart_select_group,
    chart_toggle_published,
    get_chart_group_names,
    settings_update,
)
from lava_results_app.views.query.views import (
    get_query_group_names,
    get_query_names,
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
    query_include_result,
    query_list,
    query_omit_result,
    query_refresh,
    query_remove_condition,
    query_select_group,
    query_toggle_published,
)

register_converter(JobIdConverter, "job_id")

urlpatterns = (
    path("", index, name="lava_results"),
    path("query", query_list, name="lava.results.query_list"),
    path("query/+add", query_add, name="lava.results.query_add"),
    path("query/+custom", query_custom, name="lava.results.query_custom"),
    # Query model:
    # username: str
    # name: slug
    path(
        "query/~<str:username>/<slug:name>",
        query_display,
        name="lava.results.query_display",
    ),
    path(
        "query/~<str:username>/<slug:name>/+detail",
        query_detail,
        name="lava.results.query_detail",
    ),
    path(
        "query/~<str:username>/<slug:name>/+edit",
        query_edit,
        name="lava.results.query_edit",
    ),
    path(
        "query/~<str:username>/<slug:name>/+delete",
        query_delete,
        name="lava.results.query_delete",
    ),
    path(
        "query/~<str:username>/<slug:name>/+export",
        query_export,
        name="lava.results.query_export",
    ),
    path(
        "query/+export-custom",
        query_export_custom,
        name="lava.results.query_export_custom",
    ),
    path(
        "query/~<str:username>/<slug:name>/+toggle-published",
        query_toggle_published,
        name="lava.results.query_toggle_published",
    ),
    path(
        "query/~<str:username>/<slug:name>/+copy",
        query_copy,
        name="lava.results.query_copy",
    ),
    path(
        "query/~<str:username>/<slug:name>/+refresh",
        query_refresh,
        name="lava.results.query_refresh",
    ),
    path(
        "query/~<str:username>/<slug:name>/+add-condition",
        query_add_condition,
        name="lava.results.query_add_condition",
    ),
    # Condition model
    # primary key: int
    path(
        "query/~<str:username>/<slug:name>/<int:id>/+remove-condition",
        query_remove_condition,
        name="lava.results.query_remove_condition",
    ),
    path(
        "query/~<str:username>/<slug:name>/<int:id>/+edit-condition",
        query_edit_condition,
        name="lava.results.query_edit_condition",
    ),
    path(
        "query/~<str:username>/<slug:name>/+add-group",
        query_add_group,
        name="query_add_group",
    ),
    path(
        "query/~<str:username>/<slug:name>/+select-group",
        query_select_group,
        name="query_select_group",
    ),
    path(
        "query/~<str:username>/<slug:name>/<int:id>/+omit-result",
        query_omit_result,
        name="lava.results.query_omit_result",
    ),
    path(
        "query/~<str:username>/<slug:name>/<int:id>/+include-result",
        query_include_result,
        name="lava.results.query_include_result",
    ),
    path("query/get-query-groups", query_group_list, name="query_group_list"),
    path(
        "query/+get-group-names",
        get_query_group_names,
        name="get_query_group_names",
    ),
    path(
        "query/+get-query-names",
        get_query_names,
        name="lava.results.get_query_names",
    ),
    path("<job_id:job>", testjob, name="lava.results.testjob"),
    path(
        "<job_id:job>/csv",
        testjob_csv,
        name="lava.results.testjob_csv",
    ),
    path(
        "<job_id:job>/yaml",
        testjob_yaml,
        name="lava.results.testjob_yaml",
    ),
    path(
        "<job_id:job>/yaml_summary",
        testjob_yaml_summary,
        name="lava.results.testjob_yaml_summary",
    ),
    # TestSuite model
    # primary key: int
    path(
        "<job_id:job>/<str:testsuite_name>",
        suite,
        name="lava.results.suite",
    ),
    path("chart", chart_list, name="lava.results.chart_list"),
    path("chart/+add", chart_add, name="lava.results.chart_add"),
    path("chart/+custom", chart_custom, name="lava.results.chart_custom"),
    # Chart model
    # name: slug
    path(
        "chart/<slug:name>",
        chart_display,
        name="lava.results.chart_display",
    ),
    path(
        "chart/<slug:name>/+detail",
        chart_detail,
        name="lava.results.chart_detail",
    ),
    path(
        "chart/<slug:name>/+edit",
        chart_edit,
        name="lava.results.chart_edit",
    ),
    path(
        "chart/<slug:name>/+delete",
        chart_delete,
        name="lava.results.chart_delete",
    ),
    path(
        "chart/<slug:name>/+toggle-published",
        chart_toggle_published,
        name="lava.results.chart_toggle_published",
    ),
    path(
        "chart/<slug:name>/+chart-query-add",
        chart_query_add,
        name="lava.results.chart_query_add",
    ),
    # ChartQuery model
    # primary key: int
    path(
        "chart/<slug:name>/<int:id>/+chart-query-remove",
        chart_query_remove,
        name="lava.results.chart_query_remove",
    ),
    path(
        "chart/<slug:name>/<int:id>/+chart-query-edit",
        chart_query_edit,
        name="lava.results.chart_query_edit",
    ),
    path(
        "chart/<slug:name>/+add-group",
        chart_add_group,
        name="chart_add_group",
    ),
    path(
        "chart/<slug:name>/+select-group",
        chart_select_group,
        name="chart_select_group",
    ),
    path("chart/+get-chart-groups", chart_group_list, name="chart_group_list"),
    path(
        "chart/+get-group-names",
        get_chart_group_names,
        name="get_chart_group_names",
    ),
    # ChartQueryUser model
    # chart_query__id: int
    path(
        "chart/<slug:name>/<int:id>/+settings-update",
        settings_update,
        name="chart_settings_update",
    ),
    path(
        "chart/<slug:name>/+chart-query-order-update",
        chart_query_order_update,
        name="chart_query_order_update",
    ),
    path(
        "chart/<slug:name>/<int:id>/<int:result_id>/+omit-result",
        chart_omit_result,
        name="lava.results.chart_omit_result",
    ),
    # TestSet model
    # name: str
    path(
        "<job_id:job>/<str:testsuite_name>/<str:testset_name>/<str:testcase_name>",
        testset,
        name="lava.results.testset",
    ),
    path(
        "<job_id:job>/<str:testsuite_name>/csv",
        suite_csv,
        name="lava.results.suite_csv",
    ),
    path(
        "<job_id:job>/<str:testsuite_name>/stream/csv",
        suite_csv_stream,
        name="lava.results.suite_csv_stream",
    ),
    path(
        "<job_id:job>/<str:testsuite_name>/yaml",
        suite_yaml,
        name="lava.results.suite_yaml",
    ),
    path(
        "<job_id:job>/<str:testsuite_name>/+testcase-count",
        suite_testcase_count,
        name="lava.results.suite_testcase_count",
    ),
    path("testcase/<int:testcase_id_or_name>", testcase, name="lava.results.testcase"),
    path(
        "<job_id:job>/<str:testsuite_name>/<str:testcase_id_or_name>",
        testcase,
        name="lava.results.testcase",
    ),
    path(
        "testcase/<int:pk>/yaml",
        testcase_yaml,
        name="lava.results.testcase_yaml",
    ),
)
