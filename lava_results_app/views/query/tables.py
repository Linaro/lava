# -*- coding: utf-8 -*-
# Copyright (C) 2015-2018 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA.  If not, see <http://www.gnu.org/licenses/>.

import django_tables2 as tables

from lava_results_app.models import Query, TestCase, TestSuite
from lava_results_app.tables import ResultsTable, SuiteTable
from lava_scheduler_app.models import TestJob
from lava_scheduler_app.tables import JobTable
from lava_server.lavatable import LavaTable


class UserQueryTable(LavaTable):
    name = tables.Column()

    is_published = tables.Column()

    description = tables.Column()

    def render_description(self, value):
        value = " ".join(value.split(" ")[:15])
        return value.split("\n")[0]

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
        return value.split("\n")[0]

    class Meta(UserQueryTable.Meta):
        fields = ("name", "actions", "description", "owner")
        sequence = fields
        exclude = ("is_published", "query_group")


class GroupQueryTable(UserQueryTable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_columns["query_group"].visible = False

    name = tables.Column()

    actions = tables.TemplateColumn(
        template_name="lava_results_app/query_actions_field.html"
    )
    actions.orderable = False

    description = tables.Column()

    def render_description(self, value):
        value = " ".join(value.split(" ")[:15])
        return value.split("\n")[0]

    class Meta(UserQueryTable.Meta):
        fields = ("name", "actions", "description", "owner")
        sequence = fields


class QueryTestJobTable(JobTable):

    id = tables.Column(verbose_name="ID")
    actions = tables.TemplateColumn(
        template_name="lava_scheduler_app/job_actions_field.html"
    )
    actions.orderable = False
    device = tables.TemplateColumn(
        """
    <a href="{{ record.get_absolute_url }}">{{ record.hostname }}</a>
    """
    )
    device.orderable = False
    duration = tables.Column()
    duration.orderable = False
    submit_time = tables.DateColumn()
    end_time = tables.DateColumn()

    omit = tables.TemplateColumn(
        """
    <a href="{{ query.get_absolute_url }}/{{ record.id }}/+omit-result" data-toggle="confirm" data-title="Omitting results affects all charts which use this query. Are you sure you want to omit this job from query?"><span class="glyphicon glyphicon-remove"></span></a>
    """
    )
    omit.orderable = False

    def __init__(self, query, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if query and query.is_accessible_by(user):
            self.base_columns["omit"].visible = True
        else:
            self.base_columns["omit"].visible = False

    class Meta(JobTable.Meta):
        model = TestJob
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
    <a href="{{ query.get_absolute_url }}/{{ record.id }}/+omit-result" data-toggle="confirm" data-title="Omitting results affects all charts which use this query. Are you sure you want to omit this test case from query?"><span class="glyphicon glyphicon-remove"></span></a>
    """
    )
    omit.orderable = False

    def __init__(self, query, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if query and query.is_accessible_by(user):
            self.base_columns["omit"].visible = True
        else:
            self.base_columns["omit"].visible = False

    class Meta(SuiteTable.Meta):
        model = TestCase
        attrs = {"class": "table table-hover", "id": "query-results-table"}
        per_page_field = "length"
        exclude = ["metadata"]


class QueryTestSuiteTable(ResultsTable):

    name = tables.TemplateColumn(
        """
    <a href="{{ record.get_absolute_url }}">{{ record.name }}</a>
    """
    )

    omit = tables.TemplateColumn(
        """
    <a href="{{ query.get_absolute_url }}/{{ record.id }}/+omit-result" data-toggle="confirm" data-title="Omitting results affects all charts which use this query. Are you sure you want to omit this test suite from query?"><span class="glyphicon glyphicon-remove"></span></a>
    """
    )
    omit.orderable = False

    def __init__(self, query, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if query and query.is_accessible_by(user):
            self.base_columns["omit"].visible = True
        else:
            self.base_columns["omit"].visible = False

    class Meta(ResultsTable.Meta):
        model = TestSuite
        attrs = {"class": "table table-hover", "id": "query-results-table"}
        per_page_field = "length"
