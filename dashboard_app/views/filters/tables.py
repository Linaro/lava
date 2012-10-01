# Copyright (C) 2010-2011 Linaro Limited
#
# Author: Michael Hudson-Doyle <michael.hudson@linaro.org>
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

import operator

from django.utils.html import escape
from django.utils.safestring import mark_safe

from django_tables2 import Column, TemplateColumn

from lava.utils.data_tables.tables import DataTablesTable

from dashboard_app.models import (
    TestRunFilter,
    TestRunFilterSubscription,
    )

class UserFiltersTable(DataTablesTable):

    name = TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">{{ record.name }}</a>
    ''')

    bundle_streams = TemplateColumn('''
    {% for r in record.bundle_streams.all %}
        {{r.pathname}} <br />
    {% endfor %}
    ''')

    build_number_attribute = Column()
    def render_build_number_attribute(self, value):
        if not value:
            return ''
        return value

    attributes = TemplateColumn('''
    {% for a in record.attributes.all %}
    {{ a }}  <br />
    {% endfor %}
    ''')

    test = TemplateColumn('''
      <table style="border-collapse: collapse">
        <tbody>
          {% for test in record.tests.all %}
          <tr>
            <td>
              {{ test.test }}
            </td>
            <td>
              {% for test_case in test.all_case_names %}
              {{ test_case }}
              {% empty %}
              <i>any</i>
              {% endfor %}
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    ''')

    subscription = Column()
    def render_subscription(self, record):
        try:
            sub = TestRunFilterSubscription.objects.get(
                user=self.user, filter=record)
        except TestRunFilterSubscription.DoesNotExist:
            return "None"
        else:
            return sub.get_level_display()

    public = Column()

    def get_queryset(self, user):
        return TestRunFilter.objects.filter(owner=user)


class PublicFiltersTable(UserFiltersTable):

    name = TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">~{{ record.owner.username }}/{{ record.name }}</a>
    ''')

    def __init__(self, *args, **kw):
        super(PublicFiltersTable, self).__init__(*args, **kw)
        del self.base_columns['public']

    def get_queryset(self):
        return TestRunFilter.objects.filter(public=True)



class TestRunColumn(Column):
    def render(self, record):
        # This column is only rendered if we don't really expect
        # record.test_runs to be very long...
        links = []
        trs = [tr for tr in record.test_runs if tr.test.test_id == self.verbose_name]
        for tr in trs:
            text = '%s / %s' % (tr.denormalization.count_pass, tr.denormalization.count_all())
            links.append('<a href="%s">%s</a>' % (tr.get_absolute_url(), text))
        return mark_safe('&nbsp;'.join(links))


class SpecificCaseColumn(Column):
    def __init__(self, verbose_name, test_case_id):
        super(SpecificCaseColumn, self).__init__(verbose_name)
        self.test_case_id = test_case_id
    def render(self, record):
        r = []
        for result in record.specific_results:
            if result.test_case_id != self.test_case_id:
                continue
            if result.result == result.RESULT_PASS and result.units:
                s = '%s %s' % (result.measurement, result.units)
            else:
                s = result.RESULT_MAP[result.result]
            r.append('<a href="' + result.get_absolute_url() + '">'+s+'</a>')
        return mark_safe(', '.join(r))


class BundleColumn(Column):
    def render(self, record):
        return mark_safe('<a href="' + record.bundle.get_absolute_url() + '">' + escape(record.bundle.content_filename) + '</a>')


class FilterTable(DataTablesTable):
    def __init__(self, *args, **kwargs):
        kwargs['template'] = 'dashboard_app/filter_results_table.html'
        super(FilterTable, self).__init__(*args, **kwargs)
        match_maker = self.data.queryset
        self.base_columns['tag'].verbose_name = match_maker.key_name
        bundle_stream_col = self.base_columns.pop('bundle_stream')
        bundle_col = self.base_columns.pop('bundle')
        tag_col = self.base_columns.pop('tag')
        self.complex_header = False
        if match_maker.filter_data['tests']:
            del self.base_columns['passes']
            del self.base_columns['total']
            for i, t in enumerate(reversed(match_maker.filter_data['tests'])):
                if len(t.all_case_names()) == 0:
                    col = TestRunColumn(mark_safe(t.test.test_id))
                    self.base_columns.insert(0, 'test_run_%s' % i, col)
                elif len(t.all_case_names()) == 1:
                    n = t.test.test_id + ':' + t.all_case_names()[0]
                    col = SpecificCaseColumn(mark_safe(n), t.all_case_ids()[0])
                    self.base_columns.insert(0, 'test_run_%s_case' % i, col)
                else:
                    col0 = SpecificCaseColumn(mark_safe(t.all_case_names()[0]), t.all_case_ids()[0])
                    col0.in_group = True
                    col0.first_in_group = True
                    col0.group_length = len(t.all_case_names())
                    col0.group_name = mark_safe(t.test.test_id)
                    self.complex_header = True
                    self.base_columns.insert(0, 'test_run_%s_case_%s' % (i, 0), col0)
                    for j, n in enumerate(t.all_case_names()[1:], 1):
                        col = SpecificCaseColumn(mark_safe(n), t.all_case_ids()[j])
                        col.in_group = True
                        col.first_in_group = False
                        self.base_columns.insert(j, 'test_run_%s_case_%s' % (i, j), col)
        else:
            self.base_columns.insert(0, 'bundle', bundle_col)
        if len(match_maker.filter_data['bundle_streams']) > 1:
            self.base_columns.insert(0, 'bundle_stream', bundle_stream_col)
        self.base_columns.insert(0, 'tag', tag_col)

    tag = Column()

    def render_bundle_stream(self, record):
        bundle_streams = set(tr.bundle.bundle_stream for tr in record.test_runs)
        links = []
        for bs in sorted(bundle_streams, key=operator.attrgetter('pathname')):
            links.append('<a href="%s">%s</a>' % (
                bs.get_absolute_url(), escape(bs.pathname)))
        return mark_safe('<br />'.join(links))
    bundle_stream = Column(mark_safe("Bundle Stream(s)"))

    def render_bundle(self, record):
        bundles = set(tr.bundle for tr in record.test_runs)
        links = []
        for b in sorted(bundles, key=operator.attrgetter('uploaded_on')):
            links.append('<a href="%s">%s</a>' % (
                b.get_absolute_url(), escape(b.content_filename)))
        return mark_safe('<br />'.join(links))
    bundle = Column(mark_safe("Bundle(s)"))

    passes = Column(accessor='pass_count')
    total = Column(accessor='result_count')

    def get_queryset(self, user, filter):
        return filter.get_test_runs(user)

    datatable_opts = {
        "sPaginationType": "full_numbers",
        "iDisplayLength": 25,
        "bSort": False,
        }


class FilterPreviewTable(FilterTable):
    def get_queryset(self, user, form):
        return form.get_test_runs(user)

    datatable_opts = FilterTable.datatable_opts.copy()
    datatable_opts.update({
        "iDisplayLength": 10,
        })
