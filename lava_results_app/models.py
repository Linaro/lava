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
# along with Lava Server.  If not, see <http://www.gnu.org/licenses/>.


"""
Database models of the LAVA Results

    results/<job-ID>/<lava-suite-name>/<lava-test-set>/<lava-test-case>
    results/<job-ID>/<lava-suite-name>/<lava-test-case>

TestSuite is based on the test definition
TestSet can be enabled within a test definition run step
TestCase is a single lava-test-case record or Action result.
"""

import yaml
import urllib
import logging

from django.contrib.auth.models import User, Group
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models, IntegrityError
from django.db.models import Q
from django_restricted_resource.models import RestrictedResource
from django.utils.translation import ugettext_lazy as _

from lava_scheduler_app.models import TestJob
from lava_results_app.utils import help_max_length

# TODO: this may need to be ported - clashes if redefined
from dashboard_app.models import NamedAttribute


class TestSuite(models.Model):
    """
    Result suite of a pipeline job.
    Top level grouping of results from a job.
    Directly linked to a single TestJob, the job can have multiple TestSets.
    """
    job = models.ForeignKey(
        TestJob,
        related_name='test_suites'
    )
    name = models.CharField(
        verbose_name=u'Suite name',
        blank=True,
        null=True,
        default=None,
        max_length=200
    )

    def get_absolute_url(self):
        """
        Web friendly name for the test suite
        """
        return urllib.quote("/results/%s/%s" % (self.job.id, self.name))

    def __unicode__(self):
        """
        Human friendly name for the test suite
        """
        return _(u"Test Suite {0}/{1}").format(self.job.id, self.name)


class TestSet(models.Model):
    """
    Sets collate result cases under an arbitrary text label.
    Not all cases have a TestSet
    """
    id = models.AutoField(primary_key=True)

    name = models.CharField(
        verbose_name=u'Suite name',
        blank=True,
        null=True,
        default=None,
        max_length=200
    )

    suite = models.ForeignKey(
        TestSuite,
        related_name='test_sets'
    )

    def get_absolute_url(self):
        return urllib.quote("/results/%s/%s/%s" % (
            self.suite.job.id,
            self.suite.name,
            self.name
        ))

    def __unicode__(self):
        return _(u"Test Set {0}/{1}/{2}").format(
            self.suite.job.id,
            self.suite.name,
            self.name)


class TestCase(models.Model):
    """
    Result of an individual test case.
    lava-test-case or action result
    """
    RESULT_PASS = 0
    RESULT_FAIL = 1
    RESULT_SKIP = 2
    RESULT_UNKNOWN = 3

    RESULT_REVERSE = {
        RESULT_PASS: 'pass',
        RESULT_FAIL: 'fail',
        RESULT_SKIP: 'skip',
        RESULT_UNKNOWN: 'unknown'
    }

    RESULT_MAP = {
        'pass': RESULT_PASS,
        'fail': RESULT_FAIL,
        'skip': RESULT_SKIP,
        'unknown': RESULT_UNKNOWN
    }

    name = models.TextField(
        blank=True,
        help_text=help_max_length(100),
        verbose_name=_(u"Name"))

    units = models.TextField(
        blank=True,
        help_text=(_("""Units in which measurement value should be
                     interpreted, for example <q>ms</q>, <q>MB/s</q> etc.
                     There is no semantic meaning inferred from the value of
                     this field, free form text is allowed. <br/>""") +
                   help_max_length(100)),
        verbose_name=_(u"Units"))

    result = models.PositiveSmallIntegerField(
        verbose_name=_(u"Result"),
        help_text=_(u"Result classification to pass/fail group"),
        choices=(
            (RESULT_PASS, _(u"Test passed")),
            (RESULT_FAIL, _(u"Test failed")),
            (RESULT_SKIP, _(u"Test skipped")),
            (RESULT_UNKNOWN, _(u"Unknown outcome")))
    )

    measurement = models.CharField(
        blank=True,
        max_length=512,
        help_text=_(u"Arbitrary value that was measured as a part of this test."),
        null=True,
        verbose_name=_(u"Measurement"),
    )

    metadata = models.CharField(
        blank=True,
        max_length=1024,
        help_text=_(u"Metadata collected by the pipeline action, stored as YAML."),
        null=True,
        verbose_name=_(u"Action meta data as a YAML string")
    )

    suite = models.ForeignKey(
        TestSuite,
        related_name='test_cases'
    )

    test_set = models.ForeignKey(
        TestSet,
        related_name='test_cases',
        null=True,
        blank=True,
        default=None
    )

    logged = models.DateTimeField(
        auto_now=True
    )

    @property
    def action_metadata(self):
        if not self.metadata:
            return None
        try:
            ret = yaml.load(self.metadata)
        except yaml.YAMLError:
            return None
        return ret

    @property
    def action_data(self):
        action_data = ActionData.objects.filter(testcase=self)
        if not action_data:
            return None
        return action_data[0]

    def get_absolute_url(self):
        if self.test_set:
            return urllib.quote("/results/%s/%s/%s/%s" % (
                self.suite.job.id, self.suite.name, self.test_set.name, self.name))
        else:
            return urllib.quote("/results/%s/%s/%s" % (
                self.suite.job.id, self.suite.name, self.name))

    def _get_value(self):
        if self.measurement:
            value = "%s" % self.measurement
            if self.units:
                value = "%s%s" % (self.measurement, self.units)
        elif self.metadata:
            value = self.metadata
        else:
            value = self.RESULT_REVERSE[self.result]
        return value

    def __unicode__(self):
        """
        results/<job-ID>/<lava-suite-name>/<lava-test-set>/<lava-test-case>
        results/<job-ID>/<lava-suite-name>/<lava-test-case>
        :return: a name acting as a mimic of the URL
        """
        value = self._get_value()
        if self.test_set:
            # the set already includes the job & suite in the set name
            return _(u"Test Case {0}/{1}/{2}/{3} {4}").format(
                self.suite.job.id,
                self.suite.name,
                self.test_set.name,
                self.name,
                value
            )
        return _(u"Test Case {0}/{1}/{2} {3}").format(
            self.suite.job.id,
            self.suite.name,
            self.name,
            value
        )

    @property
    def result_code(self):
        """
        Stable textual result code that does not depend on locale
        """
        return self.RESULT_REVERSE[self.result]


class MetaType(models.Model):
    """
    name will be a label, like a deployment type (NFS) or a boot type (bootz)
    """
    DEPLOY_TYPE = 0
    BOOT_TYPE = 1
    TEST_TYPE = 2
    DIAGNOSTIC_TYPE = 3
    FINALIZE_TYPE = 4
    UNKNOWN_TYPE = 5

    TYPE_CHOICES = {
        DEPLOY_TYPE: 'deploy',
        BOOT_TYPE: 'boot',
        TEST_TYPE: 'test',
        DIAGNOSTIC_TYPE: 'diagnostic',
        FINALIZE_TYPE: 'finalize',
        UNKNOWN_TYPE: 'unknown'
    }

    TYPE_MAP = {
        'deploy': DEPLOY_TYPE,
        'boot': BOOT_TYPE,
        'test': TEST_TYPE,
        'diagnostic': DIAGNOSTIC_TYPE,
        'finalize': FINALIZE_TYPE,
        'unknown': UNKNOWN_TYPE,
    }

    # the YAML keys which determine the type as per the Strategy class.
    # FIXME: lookup with classmethods?
    section_names = {
        DEPLOY_TYPE: 'to',
        BOOT_TYPE: 'method',
    }

    name = models.CharField(max_length=32)
    metatype = models.PositiveIntegerField(
        verbose_name=_(u"Type"),
        help_text=_(u"metadata action type"),
        choices=(
            (DEPLOY_TYPE, _(u"deploy")),
            (BOOT_TYPE, _(u"boot")),
            (TEST_TYPE, _(u"test")),
            (DIAGNOSTIC_TYPE, _(u"diagnostic")),
            (FINALIZE_TYPE, _(u"finalize")),
            (UNKNOWN_TYPE, _(u"unknown type")))
    )

    def __unicode__(self):
        return _(u"Name: {0} Type: {1}").format(
            self.name,
            self.TYPE_CHOICES[self.metatype])

    @classmethod
    def get_section(cls, section):
        if section not in MetaType.TYPE_MAP:
            return None
        return MetaType.TYPE_MAP[section]

    @classmethod
    def get_type_name(cls, section, definition):
        logger = logging.getLogger('lava_results_app')
        data = [action for action in definition['actions'] if section in action]
        if not data:
            logger.debug('get_type_name: skipping %s' % section)
            return None
        data = data[0][section]
        if section in MetaType.TYPE_MAP:
            if MetaType.TYPE_MAP[section] in MetaType.section_names:
                return data[MetaType.section_names[MetaType.TYPE_MAP[section]]]


class TestData(models.Model):
    """
    Static metadata gathered from the test definition and device dictionary
    Maps data from the definition and the test job logs into database fields.
    metadata is created between job submission and job scheduling, so is
    available for result processing when the job is running.
    """

    testjob = models.ForeignKey(TestJob, related_name='test_data')

    # Attributes

    attributes = generic.GenericRelation(NamedAttribute)

    # Attachments

    attachments = generic.GenericRelation('Attachment')

    def __unicode__(self):
        return _(u"TestJob {0}").format(self.testjob.id)


class ActionData(models.Model):
    """
    When TestData creates a new item, the level and name
    of that item are created and referenced.
    Other actions are ignored.
    Avoid storing the description or definition here, use a
    viewer and pass the action_level and description_line.
    This class forms the basis of the log file viewer as well as tying
    the submission yaml to the pipeline description to the metadata and the results.
    """
    action_name = models.CharField(
        max_length=100,
        blank=False, null=False)
    action_level = models.CharField(
        max_length=32,
        blank=False, null=False
    )
    action_summary = models.CharField(
        max_length=100,
        blank=False, null=False)
    action_description = models.CharField(
        max_length=200,
        blank=False, null=False)
    # each actionlevel points at a single MetaType, then to a single TestData and TestJob
    meta_type = models.ForeignKey(MetaType, related_name='actionlevels')
    testdata = models.ForeignKey(
        TestData, blank=True, null=True,
        related_name='actionlevels')
    yaml_line = models.PositiveIntegerField(blank=True, null=True)
    description_line = models.PositiveIntegerField(blank=True, null=True)
    # direct pointer to the section of the complete log.
    log_section = models.CharField(
        max_length=50,
        blank=True, null=True)
    # action.duration - actual amount of time taken
    duration = models.DecimalField(
        decimal_places=2,
        max_digits=8,  # enough for just over 11 days, 9 would be 115 days
        blank=True, null=True)
    # timeout.duration - amount of time allowed before timeout
    timeout = models.PositiveIntegerField(blank=True, null=True)
    # maps a TestCase back to the Job metadata and description
    testcase = models.ForeignKey(
        TestCase, blank=True, null=True,
        related_name='actionlevels'
    )
    # only retry actions set a count or max_retries
    count = models.PositiveIntegerField(blank=True, null=True)
    max_retries = models.PositiveIntegerField(blank=True, null=True)

    def __unicode__(self):
        return _(u"{0} {1} Level {2}, Meta {3}").format(
            self.testdata,
            self.action_name,
            self.action_level,
            self.meta_type)


class QueryGroup(models.Model):

    name = models.SlugField(max_length=1024, unique=True)

    def __unicode__(self):
        return self.name


QUERY_CONTENT_TYPES = (
    ("testjob", "lava_scheduler_app"),
    ("testcase", "lava_results_app"),
    ("testsuite", "lava_results_app"),
    ("testset", "lava_results_app")
)


class Query(models.Model):

    owner = models.ForeignKey(User)

    group = models.ForeignKey(
        Group,
        default=None,
        null=True,
        on_delete=models.SET_NULL)

    name = models.SlugField(
        max_length=1024,
        help_text=("The <b>name</b> of a query is used to refer to it in the "
                   "web UI."))

    description = models.TextField(blank=True, null=True)

    query_group = models.ForeignKey(
        QueryGroup,
        default=None,
        null=True,
        on_delete=models.CASCADE)

    content_type = models.ForeignKey(
        ContentType,
        limit_choices_to=Q(model__in=['testsuite', 'testset', 'testjob']) | (Q(app_label='lava_results_app') & Q(model='testcase')),
        verbose_name='Query object set'
    )

    @property
    def owner_name(self):
        return '~%s/%s' % (self.owner.username, self.name)

    class Meta:
        unique_together = (('owner', 'name'))

    is_published = models.BooleanField(
        default=False,
        verbose_name='Published')

    # TODO: Check how this is done in image reports 2.0.
    group_by_attribute = models.CharField(
        blank=True,
        null=True,
        max_length=20,
        verbose_name='group by attribute')

    target_goal = models.DecimalField(
        blank=True,
        decimal_places=5,
        max_digits=10,
        null=True,
        verbose_name='Target goal')

    def __unicode__(self):
        return "<Query ~%s/%s>" % (self.owner.username, self.name)

    @classmethod
    def get_results(cls, content_type, conditions):

        filters = {}

        for condition in conditions:

            # Handle different table conditions.
            if condition.table != content_type:
                filter_key = '{0}__{1}'.format(condition.table.model,
                                               condition.field)
            else:
                filter_key = condition.field

            # Handle conditions through foreign key.
            fk_model = _get_foreign_key_model(condition.table.model_class(),
                                              condition.field)
            # FIXME: There might be some other models which don't have 'name'
            # as the default search field.
            if fk_model:
                if fk_model.__name__ == "User":
                    filter_key = '{0}__username'.format(filter_key)
                elif fk_model.__name__ == "Device":
                    filter_key = '{0}__hostname'.format(filter_key)
                else:
                    filter_key = '{0}__name'.format(filter_key)

            # Handle conditions with choice fields.
            condition_field_cls = condition.table.model_class()._meta.get_field_by_name(condition.field)[0]
            if condition_field_cls.choices:
                choices_reverse = dict(
                    (value, key) for key, value in dict(
                        condition_field_cls.choices).items())
                try:
                    condition.value = choices_reverse[condition.value]
                except KeyError:
                    raise QueryConditionChoiceError()

            # Add operator.
            filter_key = '{0}__{1}'.format(filter_key, condition.operator)

            filters[filter_key] = condition.value
        query_results = content_type.model_class().objects.filter(
            **filters)
        return query_results

    @models.permalink
    def get_absolute_url(self):
        return (
            "lava_results_app.views.query.views.query_display",
            [self.owner.username, self.name])


class QueryCondition(models.Model):

    table = models.ForeignKey(
        ContentType,
        limit_choices_to=Q(model__in=[
            'testsuite', 'testset', 'testjob', 'namedattribute']) | (
                Q(app_label='lava_results_app') & Q(model='testcase')),
        verbose_name='Condition model'
    )

    query = models.ForeignKey(
        Query,
    )

    field = models.CharField(
        max_length=50,
        verbose_name='Field name'
    )

    operator = models.CharField(
        verbose_name=_(u"Operator"),
        max_length=20,
        choices=(
            (u"exact", _(u"Exact match")),
            (u"iexact", _(u"Case-insensitive match")),
            (u"icontains", _(u"Contains")),
            (u"gt", _(u"Greater than")),
            (u"lt", _(u"Less than")),
        )
    )

    value = models.CharField(
        max_length=50,
        verbose_name='Field value',
    )


def _get_foreign_key_model(model, fieldname):
    """ Returns model if field is foreign key, otherwise None. """
    field_object, model, direct, m2m = model._meta.get_field_by_name(fieldname)
    if not m2m and direct and isinstance(field_object, models.ForeignKey):
        return field_object.rel.to
    return None
