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
from collections import OrderedDict
from lava.utils.lavatable import LavaTable
from lava_results_app.models import (
    Query,
    QueryCondition,
    TestCase,
    TestSuite,
    TestSet,
)

from lava_scheduler_app.models import TestJob
from lava_scheduler_app.tables import (
    JobTable,
    DateColumn,
    TagsColumn,
    RestrictedIDLinkColumn
)


class UserQueryTable(LavaTable):

    def __init__(self, *args, **kwargs):
        super(UserQueryTable, self).__init__(*args, **kwargs)
        self.length = 10

    name = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">{{ record.name }}</a>
    ''')

    is_published = tables.Column()

    description = tables.Column()

    def render_description(self, value):
        value = ' '.join(value.split(" ")[:15])
        return value.split("\n")[0]

    user = tables.TemplateColumn('''
    {{ record.user.username }}
    ''')

    query_group = tables.Column()

    view = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}/+detail">view</a>
    ''')
    view.orderable = False

    remove = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}/+delete" onclick="return confirm('Are you sure you want to delete this Query?');">remove</a>
    ''')
    remove.orderable = False

    class Meta(LavaTable.Meta):
        model = Query
        fields = (
            'name', 'is_published', 'description',
            'query_group', 'user', 'view', 'remove'
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

    name = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">{{ record.name }}</a>
    ''')

    description = tables.Column()

    def render_description(self, value):
        value = ' '.join(value.split(" ")[:15])
        return value.split("\n")[0]

    class Meta(UserQueryTable.Meta):
        fields = (
            'name', 'description', 'user',
        )
        sequence = fields
        exclude = (
            'is_published', 'view', 'remove', 'query_group'
        )


class GroupQueryTable(UserQueryTable):

    def __init__(self, *args, **kwargs):
        super(GroupQueryTable, self).__init__(*args, **kwargs)
        self.length = 10
        self.base_columns['query_group'].visible = False

    name = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">{{ record.name }}</a>
    ''')

    description = tables.Column()

    def render_description(self, value):
        value = ' '.join(value.split(" ")[:15])
        return value.split("\n")[0]

    class Meta(UserQueryTable.Meta):
        fields = (
            'name', 'description', 'user',
        )
        sequence = fields


class QueryTestJobTable(JobTable):

    id = RestrictedIDLinkColumn(verbose_name="ID", accessor="id")
    device = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">{{ record.hostname }}</a>
    ''')
    device.orderable = False
    duration = tables.Column()
    duration.orderable = False
    submit_time = DateColumn()
    end_time = DateColumn()

    def __init__(self, *args, **kwargs):
        super(QueryTestJobTable, self).__init__(*args, **kwargs)
        self.length = 25

    class Meta(JobTable.Meta):
        model = TestJob
        attrs = {"class": "table table-hover", "id": "query-results-table"}
        per_page_field = "length"
        queries = {}


class QueryTestCaseTable(LavaTable):

    name = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">{{ record.name }}</a>
    ''')

    def __init__(self, data, *args, **kwargs):
        super(QueryTestCaseTable, self).__init__(data, *args, **kwargs)
        self.length = 25

    class Meta:
        model = TestCase
        attrs = {"class": "table table-hover", "id": "query-results-table"}
        per_page_field = "length"
        exclude = [
            'metadata',
        ]


class QueryTestSuiteTable(LavaTable):

    name = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">{{ record.name }}</a>
    ''')

    def __init__(self, data, *args, **kwargs):
        super(QueryTestSuiteTable, self).__init__(data, *args, **kwargs)
        self.length = 25

    class Meta:
        model = TestSuite
        attrs = {"class": "table table-hover", "id": "query-results-table"}
        per_page_field = "length"


class QueryTestSetTable(LavaTable):

    name = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">{{ record.name }}</a>
    ''')

    def __init__(self, data, *args, **kwargs):
        super(QueryTestSetTable, self).__init__(data, *args, **kwargs)
        self.length = 25

    class Meta:
        model = TestSet
        attrs = {"class": "table table-hover", "id": "query-results-table"}
        per_page_field = "length"
