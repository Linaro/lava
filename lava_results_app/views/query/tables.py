# Copyright (C) 2015-2018 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import django_tables2 as tables
from django.conf import settings

from lava_results_app.models import Query, TestCase
from lava_results_app.tables import SuiteTable
from lava_scheduler_app.tables_jobs import AllJobsTable
from lava_server.lavatable import LavaTable


class UserQueryTable(LavaTable):
    name = tables.Column()

    is_published = tables.Column()

    description = tables.Column()

    def render_description(self, value):
        value = " ".join(value.split(" ")[:15])
        return value.split("\n", maxsplit=1)[0]

    owner = tables.TemplateColumn(
        """
    {{ record.owner.username }}
    """
    )

    query_group = tables.Column()

    actions = tables.TemplateColumn(
        template_name="lava_results_app/query_actions_field.html"
    )
    actions.orderable = False

    last_updated = tables.TemplateColumn(
        """
    {% if record.is_live %}{% now "DATETIME_FORMAT" %}_live{% elif not record.last_updated %}Never{% else %}{{ record.last_updated }}{% endif %}
    """
    )

    class Meta(LavaTable.Meta):
        model = Query
        fields = (
            "name",
            "actions",
            "is_published",
            "description",
            "query_group",
            "owner",
            "last_updated",
        )
        sequence = fields
        searches = {"name": "contains", "description": "contains"}


class OtherQueryTable(UserQueryTable):
    name = tables.Column()

    actions = tables.TemplateColumn(
        template_name="lava_results_app/query_actions_field.html"
    )
    actions.orderable = False

    description = tables.Column()

    def render_description(self, value):
        value = " ".join(value.split(" ")[:15])
        return value.split("\n", maxsplit=1)[0]

    class Meta(UserQueryTable.Meta):
        fields = ("name", "actions", "description", "owner")
        sequence = fields
        exclude = ("is_published", "query_group")


class GroupQueryTable(UserQueryTable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.columns["query_group"].column.visible = False

    name = tables.Column()

    actions = tables.TemplateColumn(
        template_name="lava_results_app/query_actions_field.html"
    )
    actions.orderable = False

    description = tables.Column()

    def render_description(self, value):
        value = " ".join(value.split(" ")[:15])
        return value.split("\n", maxsplit=1)[0]

    class Meta(UserQueryTable.Meta):
        fields = ("name", "actions", "description", "owner")
        sequence = fields


class QueryTestJobTable(AllJobsTable):
    omit = tables.TemplateColumn(
        """
    {% if query %}
        <a href="{% url 'lava.results.query_omit_result' query.owner.username query.name record.id %}"
            data-toggle="confirm"
            data-title="Omitting results affects all charts which use this query. Are you sure you want to omit this job from query?">
            <span class="glyphicon glyphicon-remove"></span>
        </a>
    {% endif %}
    """,
        orderable=False,
    )

    def __init__(self, query, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if query and query.is_accessible_by(user):
            self.columns["omit"].column.visible = True
        else:
            self.columns["omit"].column.visible = False

    class Meta(AllJobsTable.Meta):
        attrs = {"class": "table table-hover", "id": "query-results-table"}
        per_page_field = "length"
        queries = {}


class QueryTestCaseTable(SuiteTable):
    name = tables.TemplateColumn(
        """
    <a href="{{ record.get_absolute_url }}">{{ record.name }}</a>
    """
    )

    omit = tables.TemplateColumn(
        """
    {% if query %}
        <a href="{% url 'lava.results.query_omit_result' query.owner.username query.name record.id %}"
            data-toggle="confirm"
            data-title="Omitting results affects all charts which use this query. Are you sure you want to omit this test case from query?">
            <span class="glyphicon glyphicon-remove"></span>
        </a>
    {% endif %}
    """
    )
    omit.orderable = False

    def __init__(self, query, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if query and query.is_accessible_by(user):
            self.columns["omit"].column.visible = True
        else:
            self.columns["omit"].column.visible = False

    class Meta(SuiteTable.Meta):
        model = TestCase
        attrs = {"class": "table table-hover", "id": "query-results-table"}
        per_page_field = "length"
        exclude = ["metadata"]


class QueryTestSuiteTable(LavaTable):
    job_id = tables.Column(verbose_name="Job ID")
    actions = tables.TemplateColumn(
        template_name="lava_results_app/query_suites_actions_field.html",
        orderable=False,
    )
    submitter = tables.Column(accessor="job__submitter__username", orderable=False)
    name = tables.TemplateColumn(
        "<a href='{{ record.get_absolute_url }}'>{{ record.name }}</a>",
        orderable=False,
    )
    passes = tables.Column(accessor="pk", verbose_name="Passes", orderable=False)

    def render_passes(self, record):
        return record.testcase_count("pass")

    fails = tables.Column(accessor="pk", verbose_name="Fails", orderable=False)

    def render_fails(self, record):
        return record.testcase_count("fail")

    total = tables.Column(accessor="pk", verbose_name="Totals", orderable=False)

    def render_total(self, record):
        return record.testcase_count()

    logged = tables.DateColumn(
        format=settings.DATETIME_FORMAT,
        accessor="job__start_time",
        verbose_name="Logged",
    )
    omit = tables.TemplateColumn(
        """
    {% if query %}
        <a href="{% url 'lava.results.query_omit_result' query.owner.username query.name record.id %}"
            data-toggle="confirm"
            data-title="Omitting results affects all charts which use this query. Are you sure you want to omit this test suite from query?">
            <span class="glyphicon glyphicon-remove"></span>
        </a>
    {% endif %}
    """,
        orderable=False,
    )

    def __init__(self, query, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if query and query.is_accessible_by(user):
            self.columns["omit"].column.visible = True
        else:
            self.columns["omit"].column.visible = False

    class Meta(LavaTable.Meta):
        template_name = "lazytables.html"
        attrs = {"class": "table table-hover", "id": "query-results-table"}
        per_page_field = "length"


class QueryConditionsTable(LavaTable):
    table_model = tables.Column(accessor="table__model", verbose_name="Entity")
    field = tables.Column(verbose_name="Field")
    operator = tables.Column(verbose_name="Operator")
    value = tables.Column(verbose_name="Value")
    edit = tables.TemplateColumn(
        (
            '<a class="glyphicon glyphicon-edit" aria-hidden="true" '
            'href="javascript: void(0);" '
            "onclick=\"open_condition_modal('{{ query.name }}','{{ record.id }}',"
            "'{{ record.table.id }}','{{ record.field }}',"
            "'{{ record.operator }}','{{ record.value }}');\"></a>"
        ),
        orderable=False,
    )
    remove = tables.TemplateColumn(
        (
            '<a class="glyphicon glyphicon-remove" aria-hidden="true" '
            'href="javascript:document.getElementById('
            "'query-remove-condition-{{record.id}}').submit();\"></a>"
            '<form hidden id="query-remove-condition-{{record.id}}"'
            "action=\"{% url 'lava.results.query_remove_condition' "
            'query.owner.username query.name record.id %}" '
            'method="post">{% csrf_token %}</form>'
        ),
        orderable=False,
    )

    class Meta(LavaTable.Meta):
        ...
