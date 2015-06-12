# Copyright (C) 2015 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
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
# along with Lava Dashboard.  If not, see <http://www.gnu.org/licenses/>.

# Use this file for table definitions and column rendering only
# use utils and dbutils for helpers


import django_tables2 as tables
from django.utils.safestring import mark_safe
from lava.utils.lavatable import LavaTable
from lava_scheduler_app.tables import IDLinkColumn, pklink, DateColumn
from lava_results_app.models import TestCase
from django.templatetags.static import static


class JobRestrictionColumn(IDLinkColumn):

    def render(self, record, table=None):
        # FIXME: handle job & device visibility
        return pklink(record.job)


class ResultsTable(LavaTable):
    """
    List of LAVA TestSuite results
    """

    def __init__(self, *args, **kwargs):
        super(ResultsTable, self).__init__(*args, **kwargs)
        self.length = 25

    def render_name(self, record):
        return mark_safe(
            '<a href="%s">%s</a>' % (
                record.get_absolute_url(),
                record.name))

    def render_submitter(self, record):
        return record.job.submitter

    def render_passes(self, record):
        return TestCase.objects.filter(
            suite__job=record.job,
            suite=record,
            result=TestCase.RESULT_MAP['pass']
        ).count()

    def render_fails(self, record):
        return TestCase.objects.filter(
            suite__job=record.job,
            suite=record,
            result=TestCase.RESULT_MAP['fail']
        ).count()

    def render_total(self, record):
        return TestCase.objects.filter(
            suite__job=record.job,
            suite=record,
        ).count()

    def render_logged(self, record):
        if not TestCase.objects.filter(
                suite__job=record.job,
                suite=record):
            return record.job.start_time
        return TestCase.objects.filter(
            suite__job=record.job,
            suite=record,
        )[0].logged

    job_id = JobRestrictionColumn(verbose_name='Job')
    submitter = tables.Column(accessor='job.submitter')
    name = tables.Column(verbose_name='Test Suite')
    passes = tables.Column(accessor='job', verbose_name='Passes')
    fails = tables.Column(accessor='job', verbose_name='Fails')
    total = tables.Column(accessor='job', verbose_name='Totals')
    logged = tables.Column(accessor='job', verbose_name='Logged')

    class Meta(LavaTable.Meta):
        searches = {
            'name': 'contains'
        }


class SuiteTable(LavaTable):
    """
    Details of the test sets or test cases in a test suite
    """
    def __init__(self, *args, **kwargs):
        super(SuiteTable, self).__init__(*args, **kwargs)
        self.length = 10

    name = tables.Column()
    testset = tables.Column()
    result = tables.Column()
    measurement = tables.Column()
    unit = tables.Column()
    logged = DateColumn()

    def render_name(self, record):
        return mark_safe(
            '<a href="%s">%s</a>' % (record.get_absolute_url(), record.name)
        )

    def render_result(self, record):
        if record.metadata:
            # FIXME: much more can be done here.
            if type(record.action_metadata) == str:
                return record.action_metadata
            return " ".join([key for key, _ in record.action_metadata.items() if key != 'level'])
        else:
            code = record.result_code
            image = static('lava_results_app/images/icon-%s.png' % code)
            return mark_safe(
                '<a href="%s"><img src="%s"'
                'alt="%s" width="16" height="16" border="0"/>%s</a>' % (
                    record.get_absolute_url(),
                    image,
                    code,
                    code,
                )
            )

    class Meta(LavaTable.Meta):
        searches = {
            'name': 'contains'
        }
