# Copyright (C) 2015 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
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
# along with Lava Server.  If not, see <http://www.gnu.org/licenses/>.

import django_tables2 as tables
from lava.utils.lavatable import LavaTable
from lava_results_app.models import (
    Query,
    TestCase,
    TestSuite,
)

from lava_scheduler_app.models import TestJob
from lava_scheduler_app.tables import JobTable
from lava_results_app.tables import (
    ResultsTable,
    SuiteTable
)


class UserQueryTable(LavaTable):

    def __init__(self, *args, **kwargs):
        super(UserQueryTable, self).__init__(*args, **kwargs)
        self.length = 10

    name = tables.Column()

    is_published = tables.Column()

    description = tables.Column()

    def render_description(self, value):
        value = ' '.join(value.split(" ")[:15])
        return value.split("\n")[0]

    owner = tables.TemplateColumn('''
    {{ record.owner.username }}
    ''')

    query_group = tables.Column()

    actions = tables.TemplateColumn(
        '''{% load results_accessibility_tags %}
{% is_accessible_by record request.user as is_accessible %}
<div class="text-nowrap">
  <a class="btn btn-xs btn-success {% if not record.is_live and not record.has_view %}disabled{% endif %}"
     title="{% if record.has_view or record.is_live %}View query results{% else %}Results not available, please run the query{% endif %}"
     {% if not record.is_live and not record.has_view %}
     onclick="javascript:void(0)" style="pointer-events: auto;"
     {% else %}
     href="{{ record.get_absolute_url }}"
     {% endif %}>
    <span class="glyphicon glyphicon-signal"></span>
  </a>
  <a href="{{ record.get_absolute_url }}/+detail" class="btn btn-xs btn-primary pointer-events" title="Edit query settings">
    <span class="glyphicon glyphicon-eye-open"></span>
  </a>
  <a class="btn btn-xs btn-danger {% if not is_accessible %}disabled{% endif %}"
     title="{% if is_accessible %}Delete query{% else %}You don't have sufficent persmission to delete query{% endif %}"
     {% if not is_accessible %}
     onclick="javascript:void(0)" style="pointer-events: auto;"
     {% else %}
     href="{{ record.get_absolute_url }}/+delete" data-toggle="confirm" data-title="Are you sure you want to delete this Query?"
     {% endif %}>
    <span class="glyphicon glyphicon-trash"></span>
  </a>
</div>''')
    actions.orderable = False

    last_updated = tables.TemplateColumn('''
    {% if record.is_live %}{% now "DATETIME_FORMAT" %}_live{% elif not record.last_updated %}Never{% else %}{{ record.last_updated }}{% endif %}
    ''')

    class Meta(LavaTable.Meta):
        model = Query
        fields = (
            'name', 'actions', 'is_published', 'description',
            'query_group', 'owner', 'last_updated'
        )
        sequence = fields
        searches = {
            'name': 'contains',
            'description': 'contains',
        }


class OtherQueryTable(UserQueryTable):

    def __init__(self, *args, **kwargs):
        super(OtherQueryTable, self).__init__(*args, **kwargs)
        self.length = 10

    name = tables.Column()

    description = tables.Column()

    def render_description(self, value):
        value = ' '.join(value.split(" ")[:15])
        return value.split("\n")[0]

    class Meta(UserQueryTable.Meta):
        model = Query
        fields = ()
        sequence = ('...',)
        exclude = (
            'is_published', 'query_group'
        )


class GroupQueryTable(UserQueryTable):

    def __init__(self, *args, **kwargs):
        super(GroupQueryTable, self).__init__(*args, **kwargs)
        self.length = 10
        self.base_columns['query_group'].visible = False

    name = tables.Column()

    description = tables.Column()

    def render_description(self, value):
        value = ' '.join(value.split(" ")[:15])
        return value.split("\n")[0]

    class Meta(UserQueryTable.Meta):
        fields = ()
        sequence = ('...',)


class QueryTestJobTable(JobTable):

    device = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">{{ record.hostname }}</a>
    ''')
    device.orderable = False

    omit = tables.TemplateColumn('''
    <a href="{{ query.get_absolute_url }}/{{ record.id }}/+omit-result" data-toggle="confirm" data-title="Omitting results affects all charts which use this query. Are you sure you want to omit this job from query?"><span class="glyphicon glyphicon-remove"></span></a>
    ''')
    omit.orderable = False

    def __init__(self, query, user, *args, **kwargs):
        super(QueryTestJobTable, self).__init__(*args, **kwargs)
        self.length = 25
        if query and query.is_accessible_by(user):
            self.base_columns['omit'].visible = True
        else:
            self.base_columns['omit'].visible = False

    class Meta(JobTable.Meta):
        model = TestJob
        attrs = {"class": "table table-hover", "id": "query-results-table"}
        per_page_field = "length"
        queries = {}
        fields = ()
        sequence = ('...',)


class QueryTestCaseTable(SuiteTable):

    name = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">{{ record.name }}</a>
    ''')

    omit = tables.TemplateColumn('''
    <a href="{{ query.get_absolute_url }}/{{ record.id }}/+omit-result" data-toggle="confirm" data-title="Omitting results affects all charts which use this query. Are you sure you want to omit this test case from query?"><span class="glyphicon glyphicon-remove"></span></a>
    ''')
    omit.orderable = False

    def __init__(self, query, user, *args, **kwargs):
        super(QueryTestCaseTable, self).__init__(*args, **kwargs)
        self.length = 25
        if query and query.is_accessible_by(user):
            self.base_columns['omit'].visible = True
        else:
            self.base_columns['omit'].visible = False

    class Meta(SuiteTable.Meta):
        model = TestCase
        attrs = {"class": "table table-hover", "id": "query-results-table"}
        per_page_field = "length"
        exclude = [
            'metadata',
        ]


class QueryTestSuiteTable(ResultsTable):

    name = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">{{ record.name }}</a>
    ''')

    omit = tables.TemplateColumn('''
    <a href="{{ query.get_absolute_url }}/{{ record.id }}/+omit-result" data-toggle="confirm" data-title="Omitting results affects all charts which use this query. Are you sure you want to omit this test suite from query?"><span class="glyphicon glyphicon-remove"></span></a>
    ''')
    omit.orderable = False

    def __init__(self, query, user, *args, **kwargs):
        super(QueryTestSuiteTable, self).__init__(*args, **kwargs)
        self.length = 25
        if query and query.is_accessible_by(user):
            self.base_columns['omit'].visible = True
        else:
            self.base_columns['omit'].visible = False

    class Meta(ResultsTable.Meta):
        model = TestSuite
        attrs = {"class": "table table-hover", "id": "query-results-table"}
        per_page_field = "length"
