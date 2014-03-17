# Copyright (C) 2010-2013 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

import django_tables2 as tables
from lava.utils.lavatable import LavaTable
from dashboard_app.models import ImageReport, ImageReportChart


class UserImageReportTable(LavaTable):

    def __init__(self, *args, **kwargs):
        super(UserImageReportTable, self).__init__(*args, **kwargs)
        self.length = 10

    name = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">{{ record.name }}</a>
    ''')

    is_published = tables.Column()

    description = tables.TemplateColumn('''
    {{ record.description|truncatewords:10 }}
    ''')

    user = tables.TemplateColumn('''
    {{ record.user.username }}
    ''')

    view = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}/+detail">view</a>
    ''')
    view.orderable = False

    remove = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}/+delete">remove</a>
    ''')
    remove.orderable = False

    class Meta(LavaTable.Meta):
        model = ImageReportChart
        fields = (
            'name', 'is_published', 'description',
            'user', 'view', 'remove'
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

    class Meta(UserImageReportTable.Meta):
        fields = (
            'name', 'description', 'user',
        )
        sequence = fields
        exclude = (
            'is_published', 'view', 'remove'
        )


class GroupImageReportTable(UserImageReportTable):

    def __init__(self, *args, **kwargs):
        super(GroupImageReportTable, self).__init__(*args, **kwargs)
        self.length = 10

    name = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">{{ record.name }}</a>
    ''')

    class Meta(UserImageReportTable.Meta):
        fields = (
            'name', 'description', 'user',
        )
        sequence = fields
