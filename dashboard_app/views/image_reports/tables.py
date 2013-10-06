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

from django_tables2 import Column, TemplateColumn

from lava.utils.data_tables.tables import DataTablesTable

from dashboard_app.models import ImageReport


class UserImageReportTable(DataTablesTable):

    name = TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">{{ record.name }}</a>
    ''')

    is_published = Column()

    description = TemplateColumn('''
    {{ record.description|truncatewords:10 }}
    ''')

    user = TemplateColumn('''
    {{ record.user.username }}
    ''')

    view = TemplateColumn('''
    <a href="{{ record.get_absolute_url }}/+detail">view</a>
    ''')

    remove = TemplateColumn('''
    <a href="{{ record.get_absolute_url }}/+delete">remove</a>
    ''')

    def get_queryset(self, user):
        return ImageReport.objects.filter(user=user)


class PublicImageReportTable(UserImageReportTable):

    def __init__(self, *args, **kw):
        super(PublicImageReportTable, self).__init__(*args, **kw)
        del self.base_columns['is_published']
        del self.base_columns['view']
        del self.base_columns['remove']

    def get_queryset(self, user):
        return ImageReport.objects.filter(
            is_published=True).exclude(user=user)
