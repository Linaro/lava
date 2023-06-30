# Copyright (C) 2015-2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import django_tables2 as tables
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

    def _check_job(self, record, table=None):
        """
        Slightly different purpose to RestrictedIDLinkColumn.render
        """
        user = table.context.get("request").user
        attr = f"_can_view_{user.id}"
        if hasattr(record, attr):
            return getattr(record, attr)
        ret = bool(record.job.can_view(user))
        setattr(record, attr, ret)
        return ret

    def render_submitter(self, record, table=None):
        if not self._check_job(record, table):
            return "Unavailable"
        return record.job.submitter

    def render_passes(self, record, table=None):
        if not self._check_job(record, table):
            return ""
        return record.testcase_count("pass")

    def render_fails(self, record, table=None):
        if not self._check_job(record, table):
            return ""
        return record.testcase_count("fail")

    def render_total(self, record, table=None):
        if not self._check_job(record, table):
            return ""
        return record.testcase_count()

    def render_logged(self, record, table=None):
        if not self._check_job(record, table):
            return ""
        return record.job.start_time

    job_id = tables.Column(verbose_name="Job ID")
    actions = tables.TemplateColumn(
        template_name="lava_results_app/results_actions_field.html"
    )
    actions.orderable = False
    submitter = tables.Column(accessor="job__submitter")
    name = tables.Column(verbose_name="Test Suite")
    passes = tables.Column(accessor="job", verbose_name="Passes")
    fails = tables.Column(accessor="job", verbose_name="Fails")
    total = tables.Column(accessor="job", verbose_name="Totals")
    logged = tables.Column(accessor="job", verbose_name="Logged")

    class Meta(LavaTable.Meta):
        searches = {"name": "contains"}
        sequence = {"job_id", "actions"}


class ResultsIndexTable(ResultsTable):
    job_id = tables.Column(verbose_name="Job ID")
    submitter = tables.Column(accessor="job__submitter")
    name = tables.Column(verbose_name="Test Suite")
    passes = tables.Column(accessor="job", verbose_name="Passes")
    fails = tables.Column(accessor="job", verbose_name="Fails")
    total = tables.Column(accessor="job", verbose_name="Totals")
    logged = tables.Column(accessor="job", verbose_name="Logged")

    class Meta(LavaTable.Meta):
        template_name = "lazytables.html"
        searches = {"name": "contains"}


class TestJobResultsTable(ResultsTable):
    job_id = tables.Column(verbose_name="Job ID")
    actions = tables.TemplateColumn(
        template_name="lava_results_app/suite_actions_field.html"
    )
    actions.orderable = False
    submitter = tables.Column(accessor="job__submitter")
    name = tables.Column(verbose_name="Test Suite")
    passes = tables.Column(accessor="job", verbose_name="Passes")
    fails = tables.Column(accessor="job", verbose_name="Fails")
    total = tables.Column(accessor="job", verbose_name="Totals")
    logged = tables.Column(accessor="job", verbose_name="Logged")

    class Meta(LavaTable.Meta):
        searches = {"name": "contains"}


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
