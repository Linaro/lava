# Copyright (C) 2010-2013 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
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

import django_tables2 as tables
from lava.utils.lavatable import LavaTable
from dashboard_app.models import ImageReportChart


class UserImageReportTable(LavaTable):

    def __init__(self, *args, **kwargs):
        super(UserImageReportTable, self).__init__(*args, **kwargs)
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

    image_report_group = tables.Column()

    view = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}/+detail">view</a>
    ''')
    view.orderable = False

    remove = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}/+delete" onclick="return confirm('Are you sure you want to delete this Image Report?');">remove</a>
    ''')
    remove.orderable = False

    class Meta(LavaTable.Meta):
        model = ImageReportChart
        fields = (
            'name', 'is_published', 'description',
            'image_report_group', 'user', 'view', 'remove'
        )
        sequence = fields
        searches = {
            'name': 'contains',
            'description': 'contains',
        }


class OtherImageReportTable(UserImageReportTable):

    def __init__(self, *args, **kwargs):
        super(OtherImageReportTable, self).__init__(*args, **kwargs)
        self.length = 10

    name = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">{{ record.name }}</a>
    ''')

    description = tables.Column()

    def render_description(self, value):
        value = ' '.join(value.split(" ")[:15])
        return value.split("\n")[0]

    class Meta(UserImageReportTable.Meta):
        fields = (
            'name', 'description', 'user',
        )
        sequence = fields
        exclude = (
            'is_published', 'view', 'remove', 'image_report_group'
        )


class GroupImageReportTable(UserImageReportTable):

    def __init__(self, *args, **kwargs):
        super(GroupImageReportTable, self).__init__(*args, **kwargs)
        self.length = 10
        self.base_columns['image_report_group'].visible = False

    name = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">{{ record.name }}</a>
    ''')

    description = tables.Column()

    def render_description(self, value):
        value = ' '.join(value.split(" ")[:15])
        return value.split("\n")[0]

    class Meta(UserImageReportTable.Meta):
        fields = (
            'name', 'description', 'user',
        )
        sequence = fields
