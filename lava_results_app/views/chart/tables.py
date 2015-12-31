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
from lava_results_app.models import Chart


class UserChartTable(LavaTable):

    def __init__(self, *args, **kwargs):
        super(UserChartTable, self).__init__(*args, **kwargs)
        self.length = 10

    name = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">{{ record.name }}</a>
    ''')

    is_published = tables.Column()

    description = tables.Column()

    def render_description(self, value):
        value = ' '.join(value.split(" ")[:15])
        return value.split("\n")[0]

    owner = tables.TemplateColumn('''
    {{ record.owner.username }}
    ''')

    chart_group = tables.Column()

    view = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}/+detail">view</a>
    ''')
    view.orderable = False

    remove = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}/+delete" onclick="return confirm('Are you sure you want to delete this Chart?');">remove</a>
    ''')
    remove.orderable = False

    class Meta(LavaTable.Meta):
        model = Chart
        fields = (
            'name', 'is_published', 'description',
            'chart_group', 'owner', 'view', 'remove'
        )
        sequence = fields
        searches = {
            'name': 'contains',
            'description': 'contains',
        }


class OtherChartTable(UserChartTable):

    def __init__(self, *args, **kwargs):
        super(OtherChartTable, self).__init__(*args, **kwargs)
        self.length = 10

    name = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">{{ record.name }}</a>
    ''')

    description = tables.Column()

    def render_description(self, value):
        value = ' '.join(value.split(" ")[:15])
        return value.split("\n")[0]

    class Meta(UserChartTable.Meta):
        fields = (
            'name', 'description', 'owner',
        )
        sequence = fields
        exclude = (
            'is_published', 'view', 'remove', 'chart_group'
        )


class GroupChartTable(UserChartTable):

    def __init__(self, *args, **kwargs):
        super(GroupChartTable, self).__init__(*args, **kwargs)
        self.length = 10
        self.base_columns['chart_group'].visible = False

    name = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">{{ record.name }}</a>
    ''')

    description = tables.Column()

    def render_description(self, value):
        value = ' '.join(value.split(" ")[:15])
        return value.split("\n")[0]

    class Meta(UserChartTable.Meta):
        fields = (
            'name', 'description', 'owner',
        )
        sequence = fields
