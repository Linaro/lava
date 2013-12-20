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


class OtherImageReportTable(UserImageReportTable):

    def __init__(self, *args, **kw):
        super(OtherImageReportTable, self).__init__(*args, **kw)
        del self.base_columns['is_published']
        del self.base_columns['view']
        del self.base_columns['remove']

    def get_queryset(self, user):
        # All public reports for authenticated users which are not part
        # of any group.
        # Only reports containing all public filters for non-authenticated.
        other_reports = ImageReport.objects.filter(is_published=True,
                                                   image_report_group=None)
        if user.is_authenticated():
            return other_reports
        else:
            return other_reports.exclude(
                imagereportchart__imagechartfilter__filter__public=False)


class GroupImageReportTable(OtherImageReportTable):

    def __init__(self, image_report_group, *args, **kw):
        self.image_report_group = image_report_group
        super(GroupImageReportTable, self).__init__(*args, **kw)

    def get_queryset(self, user, image_report_group):
        # Specific group reports for authenticated users.
        # Only reports containing all public filters for non-authenticated.
        group_reports = ImageReport.objects.filter(
            is_published=True,
            image_report_group=image_report_group)
        if user.is_authenticated():
            return group_reports
        else:
            return group_reports.exclude(
                imagereportchart__imagechartfilter__filter__public=False)
