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

import datetime
import operator

from django.conf import settings
from django.template import defaultfilters
from django.utils.html import escape
from django.utils.safestring import mark_safe
import django_tables2 as tables
from lava.utils.lavatable import LavaTable
from dashboard_app.filters import evaluate_filter
from dashboard_app.models import (
    Bundle,
    TestRun,
    TestRunFilter,
    TestRunFilterSubscription,
)


class UserFiltersTable(LavaTable):

    name = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">{{ record.name }}</a>
    ''')

    bundle_streams = tables.TemplateColumn('''
    {% for r in record.bundle_streams.all %}
        {{r.pathname}} <br />
    {% endfor %}
    ''')

    build_number_attribute = tables.Column()

    def render_build_number_attribute(self, value):
        if not value:
            return ''
        return value

    attributes = tables.TemplateColumn('''
    {% for a in record.attributes.all %}
    {{ a }}  <br />
    {% endfor %}
    ''')

    test = tables.TemplateColumn('''
      <table style="border-collapse: collapse">
        <tbody>
          {% for trftest in record.tests.all %}
          <tr>
            <td>
              {{ trftest.test }}
            </td>
            <td>
              {% for trftest_case in trftest.cases.all %}
              {{ trftest_case.test_case.test_case_id }}
              {% empty %}
              <i>any</i>
              {% endfor %}
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    ''')
    test.orderable = False

    subscription = tables.Column()
    subscription.orderable = False

    def render_subscription(self, record):
        try:
            sub = TestRunFilterSubscription.objects.get(
                user=self.user, filter=record)
        except TestRunFilterSubscription.DoesNotExist:
            return "None"
        else:
            return sub.get_level_display()

    public = tables.Column()

    class Meta(LavaTable.Meta):
        exclude = (
            'subscription'
        )
        searches = {
            'name': 'contains',
        }
        queries = {
            'stream_query': 'bundle_streams',
        }


class PublicFiltersTable(UserFiltersTable):

    name = tables.TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">~{{ record.owner.username }}/{{ record.name }}</a>
    ''')

    def __init__(self, *args, **kw):
        super(PublicFiltersTable, self).__init__(*args, **kw)

    class Meta(LavaTable.Meta):
        exclude = (
            'public'
        )
        searches = {
            'name': 'contains',
        }
        queries = {
            'stream_query': 'bundle_streams',
        }


class TestRunColumn(tables.Column):

    def __init__(self, verbose_name=None):
        super(TestRunColumn, self).__init__(verbose_name=verbose_name)
        self.orderable = False
        self.empty_values = ()

    def render(self, record):
        # This column is only rendered if we don't really expect
        # record.test_runs to be very long...
        links = []
        results = []
        if 'id__arrayagg' in record:
            results = TestRun.objects.filter(id__in=record['id__arrayagg'])
        trs = [tr for tr in results if tr.test.test_id == self.verbose_name]
        for tr in trs:
            text = '%s / %s' % (tr.denormalization.count_pass, tr.denormalization.count_all())
            links.append('<a href="%s">%s</a>' % (tr.get_absolute_url(), text))
        return mark_safe('&nbsp;'.join(links))


class SpecificCaseColumn(tables.Column):

    def __init__(self, test_case, match_maker, verbose_name=None):
        if verbose_name is None:
            verbose_name = mark_safe(test_case.test_case_id)
        super(SpecificCaseColumn, self).__init__(verbose_name)
        self.test_case = test_case
        self.orderable = False
        self.empty_values = ()
        self.match_maker = match_maker

    def render(self, record):
        r = []
        results = []
        if 'id__arrayagg' in record:
            results = TestRun.objects.filter(id__in=record['id__arrayagg'])[0].get_results()
        for result in results:
            if result.test_case_id != self.test_case.id:
                continue
            if result.result == result.RESULT_PASS and result.units:
                s = '%s %s' % (result.measurement, result.units)
            else:
                s = result.RESULT_MAP[result.result]
            r.append('<a href="'
                     + result.get_absolute_url() + '">'
                     + escape(s) + '</a>')
        return mark_safe(', '.join(r))


class BundleTestColumn(tables.Column):

    def __init__(self, verbose_name=None):
        super(BundleTestColumn, self).__init__(verbose_name=verbose_name)
        self.empty_values = ()

    def render(self, record):
        r = []
        if 'id__arrayagg' in record:
            runs = TestRun.objects.filter(id__in=record['id__arrayagg'])
            for run in runs:
                r.append('<a href="'
                         + run.bundle.get_absolute_url() + '">'
                         + run.bundle.content_filename
                         + '</a>')
        descriptions = sorted(set(r))
        return mark_safe(', '.join(descriptions))


class TestSummaryColumn(tables.Column):

    def __init__(self, total=False, verbose_name=None):
        super(TestSummaryColumn, self).__init__(verbose_name=verbose_name)
        self.empty_values = ()
        self.total = total

    def render(self, record):
        r = []
        tag = 'pass' if not self.total else 'total'
        if 'id__arrayagg' in record:
            runs = TestRun.objects.filter(id__in=record['id__arrayagg'])
            count = 0
            for run in runs:
                if tag in run._get_summary_results():
                    count += run._get_summary_results()[tag]
            r.append("%d" % count)
        return mark_safe(', '.join(r))


class BundleColumn(tables.Column):

    def render(self, record):
        return mark_safe('<a href="'
                         + record.bundle.get_absolute_url() + '">'
                         + escape(record.bundle.content_filename) + '</a>')


class FilterPassTable(LavaTable):

    tag = tables.Column()

    def __init__(self, data, match_maker, *args, **kwargs):
        self.base_columns['tag'].verbose_name = match_maker.key_name
        tag_col = self.base_columns.pop('tag')
        tag_col.accessor = match_maker.key
        self.complex_header = False
        if not match_maker or not match_maker.filter_data['tests']:
            raise
        self.exclude = ['passes', 'total', 'bundle']
        for i, t in enumerate(reversed(match_maker.filter_data['tests'])):
            if len(t['test_cases']) == 0:
                col = TestRunColumn(mark_safe(t['test'].test_id))
                self.base_columns.insert(0, 'test_run_%s' % i, col)
            elif len(t['test_cases']) == 1:
                tc = t['test_cases'][0]
                n = t['test'].test_id + ':' + tc.test_case_id
                col = SpecificCaseColumn(tc, match_maker=match_maker, verbose_name=n)
                self.base_columns.insert(0, 'test_run_%s_case' % i, col)
            else:
                col0 = SpecificCaseColumn(t['test_cases'][0], match_maker=match_maker)
                col0.in_group = True
                col0.first_in_group = True
                col0.group_length = len(t['test_cases'])
                col0.group_name = mark_safe(t['test'].test_id)
                self.complex_header = True
                self.base_columns.insert(0, 'test_run_%s_case_%s' % (i, 0), col0)
                for j, tc in enumerate(t['test_cases'][1:], 1):
                    col = SpecificCaseColumn(tc, match_maker=match_maker)
                    col.in_group = True
                    col.first_in_group = False
                    self.base_columns.insert(j, 'test_run_%s_case_%s' % (i, j), col)
        self.base_columns.insert(0, 'tag', tag_col)
        super(FilterPassTable, self).__init__(data, *args, **kwargs)
        self.length = 25
        self.template = 'dashboard_app/filter_results_table.html'

    def render_tag(self, value):
        if isinstance(value, datetime.datetime):
            strvalue = defaultfilters.date(value, settings.DATETIME_FORMAT)
        else:
            strvalue = value
        return mark_safe('<span data-machinetag="%s">%s</span>' % (escape(str(value)), strvalue))

    class Meta:
        model = None
        attrs = {"class": "display"}
        per_page_field = "length"
        template = 'dashboard_app/filter_results_table.html'


class FilterSummaryTable(LavaTable):

    tag = tables.Column()

    def __init__(self, data, match_maker, *args, **kwargs):
        self.base_columns['tag'].verbose_name = match_maker.key_name
        tag_col = self.base_columns.pop('tag')
        tag_col.accessor = match_maker.key
        self.complex_header = False
        total = TestSummaryColumn(total=True)
        self.base_columns.insert(0, 'total', total)
        passes = TestSummaryColumn()
        self.base_columns.insert(0, 'passes', passes)
        bundle_col = BundleTestColumn(verbose_name=mark_safe("Bundle(s)"))
        self.base_columns.insert(0, 'bundle', bundle_col)
        self.base_columns.insert(0, 'tag', tag_col)
        super(FilterSummaryTable, self).__init__(data, *args, **kwargs)
        self.length = 25
        self.template = 'dashboard_app/filter_results_table.html'

    def render_tag(self, value):
        if isinstance(value, datetime.datetime):
            strvalue = defaultfilters.date(value, settings.DATETIME_FORMAT)
        else:
            strvalue = value
        return mark_safe('<span data-machinetag="%s">%s</span>' % (escape(str(value)), strvalue))

    class Meta:
        model = None
        attrs = {"class": "display"}
        per_page_field = "length"
        template = 'dashboard_app/filter_results_table.html'


class FilterTable(tables.Table):
    """
    Deprecated - extensions looking for FilterTable need to migrate to LavaTable
    or use FilterPassTable or FilterSummaryTable.
    """
    def __init__(self, *args, **kwargs):
        super(FilterTable, self).__init__(*args, **kwargs)
        self.length = 10
        raise Exception("FilterTable is deprecated, migrate to LavaTable.")


class TestResultDifferenceTable(LavaTable):

    def __init__(self, *args, **kwargs):
        super(TestResultDifferenceTable, self).__init__(*args, **kwargs)
        self.length = 25

    test_case_id = tables.Column(verbose_name=mark_safe('test_case_id'))
    first_result = tables.TemplateColumn('''
    {% if record.first_result %}
    <img src="{{ STATIC_URL }}dashboard_app/images/icon-{{ record.first_result }}.png"
          alt="{{ record.first_result }}" width="16" height="16" border="0"/>{{ record.first_result }}
    {% else %}
    <i>missing</i>
    {% endif %}
        ''')
    second_result = tables.TemplateColumn('''
    {% if record.second_result %}
    <img src="{{ STATIC_URL }}dashboard_app/images/icon-{{ record.second_result }}.png"
          alt="{{ record.second_result }}" width="16" height="16" border="0"/>{{ record.second_result }}
    {% else %}
    <i>missing</i>
    {% endif %}
        ''')
