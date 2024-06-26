# Copyright (C) 2015-2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import django_tables2 as tables
from django.conf import settings
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe

from lava_server.lavatable import LavaTable


def results_pklink(record):
    job_id = record.pk
    complete = format_html(
        '<a class="btn btn-xs btn-success pull-right" title="test job results" href="{}">',
        record.results_link,
    )
    button = '<span class="glyphicon glyphicon-signal"></span></a>'
    return mark_safe(
        '<a href="%s" title="test job summary">%s</a>&nbsp;%s%s'
        % (record.get_absolute_url(), escape(job_id), complete, button)
    )


class ResultsTable(LavaTable):
    """
    List of LAVA TestSuite results
    """

    job_id = tables.Column(
        accessor="pk",
        verbose_name="Job ID",
        linkify=("lava.scheduler.job.detail", (tables.A("pk"),)),
    )
    actions = tables.TemplateColumn(
        template_name="lava_results_app/results_actions_field.html",
        orderable=False,
    )
    submitter = tables.Column(accessor="submitter__username", orderable=False)
    name = tables.Column(
        accessor="testsuite__name", verbose_name="Test Suite", orderable=False
    )
    passes = tables.Column(accessor="passes", verbose_name="Passes", orderable=False)
    fails = tables.Column(accessor="fails", verbose_name="Fails", orderable=False)
    total = tables.Column(accessor="totals", verbose_name="Totals", orderable=False)
    logged = tables.DateColumn(
        format=settings.DATETIME_FORMAT, accessor="start_time", verbose_name="Logged"
    )

    class Meta(LavaTable.Meta):
        template_name = "lazytables.html"
        searches = {"name": "contains"}


class TestJobResultsTable(ResultsTable):
    actions = tables.TemplateColumn(
        template_name="lava_results_app/suite_actions_field.html",
        orderable=False,
    )

    class Meta(ResultsTable.Meta):
        ...


class SuiteTable(LavaTable):
    """
    Details of the test sets or test cases in a test suite
    """

    name = tables.Column()
    test_set = tables.Column(verbose_name="Test Set")
    result = tables.Column()
    measurement = tables.Column()
    units = tables.Column()
    logged = tables.DateTimeColumn()

    def render_name(self, record):
        return format_html(
            '<a href="{}">{}</a>', record.get_absolute_url(), record.name
        )

    def render_result(self, record):
        code = record.result_code
        if code == "pass":
            icon = "ok"
        elif code == "fail":
            icon = "remove"
        else:
            icon = "minus"
        return format_html(
            '<a href="{}"><span class="glyphicon glyphicon-{}"></span> {}</a>',
            record.get_absolute_url(),
            icon,
            code,
        )

    def render_test_set(self, record):
        return format_html(
            '<a href="{}">{}</a>',
            record.test_set.get_absolute_url(),
            record.test_set.name,
        )

    class Meta(LavaTable.Meta):
        searches = {"name": "contains"}
