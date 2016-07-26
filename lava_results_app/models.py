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

import logging
import urllib
import yaml

from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes import fields
from django.contrib.contenttypes.models import ContentType
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator
)
from django.db import models, connection, transaction
from django.db.models import Q, Lookup
from django.db.models.fields import Field
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone

from lava.utils.managers import MaterializedView
from lava_scheduler_app.models import (
    TestJob,
    Device
)
from lava_scheduler_app.managers import (
    RestrictedTestJobQuerySet,
    RestrictedTestCaseQuerySet,
    RestrictedTestSuiteQuerySet
)

from lava_results_app.utils import help_max_length


class InvalidConditionsError(Exception):
    """ Raise when querying by URL has incorrect condition arguments. """


class InvalidContentTypeError(Exception):
    """ Raise when querying by URL content type (table name). """


class QueryUpdatedError(Exception):
    """ Error raised if query is updating or recently updated. """


class RefreshLiveQueryError(Exception):
    """ Error raised if refreshing the live query is attempted. """


class Queryable(object):
    """All Queryable objects should inherit this."""
    def get_passfail_results(self):
        raise NotImplementedError("Should have implemented this")

    def get_measurement_results(self):
        raise NotImplementedError("Should have implemented this")

    def get_attribute_results(self, attributes):
        raise NotImplementedError("Should have implemented this")

    def get_end_datetime(self):
        raise NotImplementedError("Should have implemented this")

    def get_xaxis_attribute(self):
        raise NotImplementedError("Should have implemented this")


@Field.register_lookup
class NotEqual(Lookup):
    # Class for __ne field lookup.
    lookup_name = 'ne'

    def as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        params = lhs_params + rhs_params
        return '%s <> %s' % (lhs, rhs), params


class QueryMaterializedView(MaterializedView):

    class Meta:
        abstract = True

    CREATE_VIEW = "CREATE MATERIALIZED VIEW %s%s AS %s;"
    DROP_VIEW = "DROP MATERIALIZED VIEW IF EXISTS %s%s;"
    REFRESH_VIEW = "REFRESH MATERIALIZED VIEW %s%s;"
    VIEW_EXISTS = "SELECT EXISTS(SELECT * FROM pg_class WHERE relname='%s%s');"
    QUERY_VIEW_PREFIX = "query_"

    @classmethod
    def create(cls, query):
        # Check if view for this query exists.
        cursor = connection.cursor()
        if not cls.view_exists(query.id):  # create view
            sql, params = Query.get_queryset(
                query.content_type,
                query.querycondition_set.all(),
                query.limit).query.sql_with_params()

            sql = sql.replace("%s", "'%s'")
            query_str = sql % params

            # TODO: handle potential exceptions here. what to do if query
            # view is not created? - new field update_status?
            query_str = cls.CREATE_VIEW % (cls.QUERY_VIEW_PREFIX,
                                           query.id, query_str)
            cursor.execute(query_str)

    @classmethod
    def refresh(cls, query_id):
        refresh_sql = cls.REFRESH_VIEW % (cls.QUERY_VIEW_PREFIX, query_id)
        cursor = connection.cursor()
        cursor.execute(refresh_sql)

    @classmethod
    def drop(cls, query_id):
        drop_sql = cls.DROP_VIEW % (cls.QUERY_VIEW_PREFIX, query_id)
        cursor = connection.cursor()
        cursor.execute(drop_sql)

    @classmethod
    def view_exists(cls, query_id):
        cursor = connection.cursor()
        cursor.execute(cls.VIEW_EXISTS % (cls.QUERY_VIEW_PREFIX, query_id))
        return cursor.fetchone()[0]

    def get_queryset(self):
        return QueryMaterializedView.objects.all()


class TestSuite(models.Model, Queryable):
    """
    Result suite of a pipeline job.
    Top level grouping of results from a job.
    Directly linked to a single TestJob, the job can have multiple TestSets.
    """

    objects = models.Manager.from_queryset(RestrictedTestSuiteQuerySet)()

    job = models.ForeignKey(
        TestJob,
    )
    name = models.CharField(
        verbose_name=u'Suite name',
        blank=True,
        null=True,
        default=None,
        max_length=200
    )

    def get_passfail_results(self):
        # Get pass fail results per lava_results_app.testsuite.
        results = {}
        results[self.name] = {
            'pass': self.testcase_set.filter(
                result=TestCase.RESULT_MAP['pass']).count(),
            'fail': self.testcase_set.filter(
                result=TestCase.RESULT_MAP['fail']).count(),
            'skip': self.testcase_set.filter(
                result=TestCase.RESULT_MAP['skip']).count(),
            'unknown': self.testcase_set.filter(
                result=TestCase.RESULT_MAP['unknown']).count()
        }
        return results

    def get_measurement_results(self):
        # Get measurement values per lava_results_app.testcase.
        results = {}

        for testcase in self.testcase_set.all():
            results[testcase.name] = {}
            results[testcase.name]['measurement'] = testcase.measurement
            results[testcase.name]['fail'] = testcase.result != TestCase.RESULT_PASS

        return results

    def get_attribute_results(self, attributes):
        # Get attribute values per lava_results_app.testsuite.
        results = {}
        attributes = [x.strip() for x in attributes.split(',')]
        for testcase in self.testcase_set.all():
            if testcase.action_metadata:
                for key in testcase.action_metadata:
                    if key in attributes and key not in results:
                        # Use only the metadata from the first testcase atm.
                        results[key] = {}
                        results[key]['fail'] = testcase.result != TestCase.RESULT_PASS
                        try:
                            results[key]['value'] = float(
                                testcase.action_metadata[key])
                        except ValueError:
                            # Ignore non-float metadata.
                            del results[key]

        return results

    def get_end_datetime(self):
        return self.job.end_time

    def get_xaxis_attribute(self, xaxis_attribute=None):

        attribute = None
        if xaxis_attribute:
            try:
                attribute = self.testcase_set.first().action_metadata[
                    xaxis_attribute]
            except:  # There's no attribute, use date.
                pass

        return attribute

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


class TestCase(models.Model, Queryable):
    """
    Result of an individual test case.
    lava-test-case or action result
    """

    objects = models.Manager.from_queryset(RestrictedTestCaseQuerySet)()

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

    RESULT_CHOICES = (
        (RESULT_PASS, _(u"Test passed")),
        (RESULT_FAIL, _(u"Test failed")),
        (RESULT_SKIP, _(u"Test skipped")),
        (RESULT_UNKNOWN, _(u"Unknown outcome"))
    )

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
        choices=RESULT_CHOICES
    )

    measurement = models.DecimalField(
        decimal_places=10,
        max_digits=30,
        blank=True,
        help_text=_(u"Arbitrary value that was measured as a part of this test."),
        null=True,
        verbose_name=_(u"Measurement"),
    )

    metadata = models.CharField(
        blank=True,
        max_length=4096,
        help_text=_(u"Metadata collected by the pipeline action, stored as YAML."),
        null=True,
        verbose_name=_(u"Action meta data as a YAML string")
    )

    suite = models.ForeignKey(
        TestSuite,
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

    def get_passfail_results(self):
        # Pass/fail charts for testcases do not make sense.
        pass

    def get_measurement_results(self):
        # Get measurement values per lava_results_app.testcase.
        results = {}
        results[self.name] = {}
        results[self.name]['measurement'] = self.measurement
        results[self.name]['fail'] = self.result != self.RESULT_PASS
        return results

    def get_attribute_results(self, attributes):
        # Get attribute values per lava_results_app.testcase.
        results = {}
        attributes = [x.strip() for x in attributes.split(',')]
        if self.action_metadata:
            for key in self.action_metadata:
                if key in attributes:
                    results[key] = {}
                    results[key]['fail'] = self.result != self.RESULT_PASS
                    try:
                        results[key]['value'] = float(
                            self.action_metadata[key])
                    except ValueError:
                        # Ignore non-float metadata.
                        del results[key]

        return results

    def get_end_datetime(self):
        return self.logged

    def get_xaxis_attribute(self, xaxis_attribute=None):

        attribute = None
        if xaxis_attribute:
            try:
                attribute = self.action_metadata[xaxis_attribute]
            except:  # There's no attribute, use date.
                pass

        return attribute

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
    for test metadata, the MetaType is just the section_name.
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
        TEST_TYPE: 'definitions',
    }

    name = models.CharField(max_length=256)
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
        logger = logging.getLogger('dispatcher-master')
        retval = None
        data = [action for action in definition['actions'] if section in action]
        if not data:
            logger.debug('get_type_name: skipping %s' % section)
            return None
        data = data[0][section]
        if section in MetaType.TYPE_MAP:
            if MetaType.TYPE_MAP[section] in MetaType.section_names:
                retval = data[MetaType.section_names[MetaType.TYPE_MAP[section]]]
        if isinstance(retval, list):
            # No simple way to collapse a long list of definitions into 255 characters
            return MetaType.section_names[MetaType.TYPE_MAP[section]]
        else:
            return retval


class NamedTestAttribute(models.Model):
    """
    Model for adding named test attributes to arbitrary other model instances.

    Example:
        class Foo(Model):
            attributes = fields.GenericRelation(NamedTestAttribute)
    """
    name = models.TextField()

    value = models.TextField()

    # Content type plumbing
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = fields.GenericForeignKey('content_type', 'object_id')

    def __unicode__(self):
        return _(u"{name}: {value}").format(
            name=self.name,
            value=self.value)

    class Meta:
        unique_together = (('object_id', 'name', 'content_type'))
        verbose_name = "metadata"


class TestData(models.Model):
    """
    Static metadata gathered from the test definition and device dictionary
    Maps data from the definition and the test job logs into database fields.
    metadata is created between job submission and job scheduling, so is
    available for result processing when the job is running.
    """

    testjob = models.ForeignKey(TestJob)

    # Attributes

    attributes = fields.GenericRelation(NamedTestAttribute)

    def __unicode__(self):
        return _(u"TestJob {0}").format(self.testjob.id)


class ActionData(models.Model):
    """
    Each Action in the pipeline has Data tracked in this model.
    One TestData object can relate to multiple ActionData objects.
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


def TestJobViewFactory(query):

    class TestJobMaterializedView(QueryMaterializedView, TestJob):

        objects = models.Manager.from_queryset(RestrictedTestJobQuerySet)()

        class Meta(QueryMaterializedView.Meta):
            db_table = '%s%s' % (QueryMaterializedView.QUERY_VIEW_PREFIX,
                                 query.id)

    return TestJobMaterializedView()


def TestCaseViewFactory(query):

    class TestCaseMaterializedView(QueryMaterializedView, TestCase):

        objects = models.Manager.from_queryset(RestrictedTestCaseQuerySet)()

        class Meta(QueryMaterializedView.Meta):
            db_table = '%s%s' % (QueryMaterializedView.QUERY_VIEW_PREFIX,
                                 query.id)

    return TestCaseMaterializedView()


def TestSuiteViewFactory(query):

    class TestSuiteMaterializedView(QueryMaterializedView, TestSuite):

        objects = models.Manager.from_queryset(RestrictedTestSuiteQuerySet)()

        class Meta(QueryMaterializedView.Meta):
            db_table = '%s%s' % (QueryMaterializedView.QUERY_VIEW_PREFIX,
                                 query.id)

    return TestSuiteMaterializedView()


class Query(models.Model):

    owner = models.ForeignKey(User)

    group = models.ForeignKey(
        Group,
        default=None,
        null=True,
        blank=True,
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
        blank=True,
        on_delete=models.CASCADE)

    limit = models.PositiveIntegerField(
        default=200,
        validators=[
            MinValueValidator(20),
        ],
        verbose_name='Results limit')

    content_type = models.ForeignKey(
        ContentType,
        limit_choices_to=Q(model__in=['testsuite', 'testjob']) | (Q(app_label='lava_results_app') & Q(model='testcase')),
        verbose_name='Query object set'
    )

    CONDITIONS_SEPARATOR = ','
    CONDITION_DIVIDER = '__'

    @property
    def owner_name(self):
        return '~%s/%s' % (self.owner.username, self.name)

    class Meta:
        unique_together = (('owner', 'name'))
        verbose_name = "query"
        verbose_name_plural = "queries"

    is_published = models.BooleanField(
        default=False,
        verbose_name='Published')

    is_live = models.BooleanField(
        default=False,
        verbose_name='Live query')

    is_changed = models.BooleanField(
        default=False,
        verbose_name='Conditions have changed')

    is_updating = models.BooleanField(
        default=False,
        editable=False,
        verbose_name='Query is currently updating')

    last_updated = models.DateTimeField(
        blank=True,
        null=True
    )

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

    is_archived = models.BooleanField(
        default=False,
        verbose_name='Archived')

    def __unicode__(self):
        return "<Query ~%s/%s>" % (self.owner.username, self.name)

    def get_results(self, user, limit=None, order_by=['-id']):
        """ Used to get query results for persistant queries.

        Limit parameter should not be used in views where django tables are
        used.
        """

        omitted_list = QueryOmitResult.objects.filter(
            query=self).values_list('object_id', flat=True)

        if self.is_live:
            return Query.get_queryset(
                self.content_type,
                self.querycondition_set.all(),
                limit, order_by=order_by).exclude(
                    id__in=omitted_list).visible_by_user(user)
        else:
            if self.content_type.model_class() == TestJob:
                view = TestJobViewFactory(self)
            elif self.content_type.model_class() == TestCase:
                view = TestCaseViewFactory(self)
            elif self.content_type.model_class() == TestSuite:
                view = TestSuiteViewFactory(self)

            return view.__class__.objects.all().exclude(
                id__in=omitted_list).order_by(*order_by).visible_by_user(
                    user)[:limit]

    @classmethod
    def get_queryset(cls, content_type, conditions, limit=None,
                     order_by=['-id']):
        """ Return list of QuerySet objects for class 'content_type'.

        Be mindful when using this method directly as it does not apply the
        visibility rules.

        This method is used for custom and live queries since they are do not
        have corresponding materialized views.

        Limit parameter should not be used in views where django tables are
        used.
        """

        logger = logging.getLogger('lava_results_app')
        filters = {}

        for condition in conditions:

            try:
                relation_string = QueryCondition.RELATION_MAP[
                    content_type.model_class()][condition.table.model_class()]
            except KeyError:
                logger.info('mapping unsupported for content types %s and %s!'
                            % (content_type.model_class(),
                               condition.table.model_class()))
                raise

            if condition.table.model_class() == NamedTestAttribute:
                # For custom attributes, need two filters since
                # we're comparing the key(name) and the value.
                filter_key_name = '{0}__name'.format(relation_string)
                filter_key_value = '{0}__value'.format(relation_string)
                filter_key_value = '{0}__{1}'.format(filter_key_value,
                                                     condition.operator)

                filters[filter_key_name] = condition.field
                filters[filter_key_value] = condition.value

            else:
                if condition.table == content_type:
                    filter_key = condition.field
                else:
                    filter_key = '{0}__{1}'.format(relation_string,
                                                   condition.field)
                # Handle conditions through relations.
                fk_model = _get_foreign_key_model(
                    condition.table.model_class(),
                    condition.field)
                # FIXME: There might be some other related models which don't
                # have 'name' as the default search field.
                if fk_model:
                    if fk_model == User:
                        filter_key = '{0}__username'.format(filter_key)
                    elif fk_model == Device:
                        filter_key = '{0}__hostname'.format(filter_key)
                    else:
                        filter_key = '{0}__name'.format(filter_key)

                # Handle conditions with choice fields.
                condition_field_obj = condition.table.model_class()._meta.\
                    get_field_by_name(condition.field)[0]
                if condition_field_obj.choices:
                    choices_reverse = dict(
                        (value, key) for key, value in dict(
                            condition_field_obj.choices).items())
                    try:
                        condition.value = choices_reverse[condition.value]
                    except KeyError:
                        logger.error(
                            'skip condition %s due to unsupported choice'
                            % condition)
                        continue

                # Handle boolean conditions.
                if condition_field_obj.__class__ == models.BooleanField:
                    if condition.value == "False":
                        condition.value = False
                    else:
                        condition.value = True

                # Add operator.
                filter_key = '{0}__{1}'.format(filter_key, condition.operator)

                filters[filter_key] = condition.value

        query_results = content_type.model_class().objects.filter(
            **filters).distinct().order_by(*order_by).extra(select={
                '%s_ptr_id' % content_type.model:
                '%s.id' % content_type.model_class()._meta.db_table})[:limit]

        return query_results

    def refresh_view(self):

        if self.is_live:
            raise RefreshLiveQueryError("Refreshing live query not permitted.")

        hour_ago = timezone.now() - timedelta(hours=1)

        with transaction.atomic():
            # Lock the selected row until the end of transaction.
            query = Query.objects.select_for_update().get(pk=self.id)
            if query.is_updating:
                raise QueryUpdatedError("query is currently updating")
            # TODO: commented out because of testing purposes.
            # elif query.last_updated and query.last_updated > hour_ago:
            #    raise QueryUpdatedError("query was recently updated (less then hour ago)")
            else:
                query.is_updating = True
                query.save()

        try:
            if not QueryMaterializedView.view_exists(self.id):
                QueryMaterializedView.create(self)
            elif self.is_changed:
                QueryMaterializedView.drop(self.id)
                QueryMaterializedView.create(self)
            else:
                QueryMaterializedView.refresh(self.id)

            self.last_updated = timezone.now()
            self.is_changed = False

        finally:
            self.is_updating = False
            self.save()

    @classmethod
    def parse_conditions(cls, content_type, conditions):
        # Parse conditions from text representation.
        if not conditions:
            return []

        conditions_objects = []
        for condition_str in conditions.split(cls.CONDITIONS_SEPARATOR):
            condition = QueryCondition()
            condition_fields = condition_str.split(cls.CONDITION_DIVIDER)
            if len(condition_fields) == 2:
                condition.table = content_type
                condition.field = condition_fields[0]
                condition.operator = QueryCondition.EXACT
                condition.value = condition_fields[1]
            elif len(condition_fields) == 3:
                condition.table = content_type
                condition.field = condition_fields[0]
                condition.operator = condition_fields[1]
                condition.value = condition_fields[2]
            elif len(condition_fields) == 4:

                try:
                    content_type = Query.get_content_type(condition_fields[0])
                except ContentType.DoesNotExist:
                    raise InvalidContentTypeError(
                        "Wrong table name in conditions parameter. " +
                        "Please refer to query docs.")

                condition.table = content_type
                condition.field = condition_fields[1]
                condition.operator = condition_fields[2]
                condition.value = condition_fields[3]

            else:
                # TODO: more validation for conditions?.
                raise InvalidConditionsError("Conditions URL incorrect. Please "
                                             "refer to query docs.")

            conditions_objects.append(condition)

        return conditions_objects

    @classmethod
    def serialize_conditions(cls, conditions):
        # Serialize conditions into string.

        conditions_list = []
        for condition in conditions:
            conditions_list.append("%s%s%s%s%s%s%s" % (
                condition.table.model,
                cls.CONDITION_DIVIDER,
                condition.field,
                cls.CONDITION_DIVIDER,
                condition.operator,
                cls.CONDITION_DIVIDER,
                condition.value
            ))

        return cls.CONDITIONS_SEPARATOR.join(conditions_list)

    @classmethod
    def get_content_type(cls, model_name):
        # Need this check because there are multiple models named 'TestCase'
        # in different apps now.
        if (model_name == ContentType.objects.get_for_model(TestCase).model):
            return ContentType.objects.get_for_model(TestCase)

        content_types = ContentType.objects.filter(model=model_name)
        if (len(content_types) == 0):
            raise InvalidContentTypeError(
                "Wrong table name in entity param. Please refer to query docs.")
        else:
            return ContentType.objects.filter(model=model_name)[0]

    @classmethod
    def validate_custom_query(cls, model_name, conditions):
        """Validate custom query content type and conditions.

        :param model_name: Content type name (entity).
        :type model_name: str
        :param conditions: Query conditions, fields and values.
        :type conditions: dict
        :raise InvalidContentTypeError model_name is not recognized.
        :raise InvalidConditionsError conditions do not have correct format.
        :return Nothing
        """
        content_type = cls.get_content_type(model_name)
        if content_type.model_class() not in QueryCondition.RELATION_MAP:
            raise InvalidContentTypeError(
                "Wrong table name in entity param. Please refer to query doc.")
        condition_list = []
        for key in conditions:
            condition_list.append("%s%s%s" % (key, cls.CONDITION_DIVIDER,
                                              conditions[key]))
        conditions = cls.CONDITIONS_SEPARATOR.join(condition_list)
        cls.parse_conditions(content_type, conditions)

    def save(self, *args, **kwargs):
        super(Query, self).save(*args, **kwargs)
        if self.is_live:
            # Drop the view.
            QueryMaterializedView.drop(self.id)

    def delete(self, *args, **kwargs):
        if not self.is_live:
            # Drop the view.
            QueryMaterializedView.drop(self.id)
        super(Query, self).delete(*args, **kwargs)

    def is_accessible_by(self, user):
        if user.is_superuser or self.owner == user or \
           self.group in user.groups.all():
            return True
        return False

    @models.permalink
    def get_absolute_url(self):
        return (
            "lava.results.query_display",
            [self.owner.username, self.name])


class QueryCondition(models.Model):

    table = models.ForeignKey(
        ContentType,
        limit_choices_to=Q(model__in=[
            'testsuite', 'testjob', 'namedtestattribute']) | (
                Q(app_label='lava_results_app') & Q(model='testcase')),
        verbose_name='Condition model'
    )

    # Map the relationship spanning.
    RELATION_MAP = {
        TestJob: {
            TestJob: None,
            TestSuite: 'testsuite',
            TestCase: 'testsuite__testcase',
            NamedTestAttribute: 'testdata__attributes',
        },
        TestSuite: {
            TestJob: 'job',
            TestCase: 'testcase',
            TestSuite: None,
            NamedTestAttribute:
                'job__testdata__attributes',
        },
        TestCase: {
            TestCase: None,
            TestJob: 'suite__job',
            TestSuite: 'suite',
            NamedTestAttribute:
                'suite__job__testdata__attributes',
        }
    }

    # Allowed fields for condition entities.
    FIELD_CHOICES = {
        TestJob: [
            "submitter", "start_time", "end_time", "status", "actual_device",
            "health_check", "user", "group", "priority", "is_pipeline"],
        TestSuite: ["name"],
        TestCase: ["name", "result", "measurement"],
        NamedTestAttribute: []
    }

    query = models.ForeignKey(
        Query,
    )

    field = models.CharField(
        max_length=50,
        verbose_name='Field name'
    )

    EXACT = 'exact'
    NOTEQUAL = 'ne'
    IEXACT = 'iexact'
    ICONTAINS = 'icontains'
    GT = 'gt'
    LT = 'lt'

    OPERATOR_CHOICES = (
        (EXACT, u"Exact match"),
        (IEXACT, u"Case-insensitive match"),
        (NOTEQUAL, u"Not equal to"),
        (ICONTAINS, u"Contains"),
        (GT, u"Greater than"),
        (LT, u"Less than"),
    )

    operator = models.CharField(
        blank=False,
        default=EXACT,
        verbose_name=_(u"Operator"),
        max_length=20,
        choices=OPERATOR_CHOICES
    )

    value = models.CharField(
        max_length=40,
        verbose_name='Field value',
    )

    def save(self, *args, **kwargs):
        super(QueryCondition, self).save(*args, **kwargs)
        if not self.query.is_live:
            self.query.is_changed = True
            self.query.save()

    def delete(self, *args, **kwargs):
        super(QueryCondition, self).delete(*args, **kwargs)
        if not self.query.is_live:
            self.query.is_changed = True
            self.query.save()

    @classmethod
    def get_condition_choices(cls, job=None):
        # Create a dict with all possible operators based on the all available
        # field types, used for validation.
        # If job is supplied, return available metadata field names as well.

        condition_choices = {}
        for model in cls.FIELD_CHOICES:
            condition_choice = {}
            condition_choice['fields'] = {}
            content_type = ContentType.objects.get_for_model(model)

            if job and model == NamedTestAttribute:
                testdata = TestData.objects.filter(testjob=job).first()
                if testdata:
                    for attribute in NamedTestAttribute.objects.filter(
                            object_id=testdata.id,
                            content_type=ContentType.objects.get_for_model(
                                TestData)):
                        condition_choice['fields'][attribute.name] = {}

            else:
                for field_name in cls.FIELD_CHOICES[model]:
                    field = {}

                    field_object = content_type.model_class()._meta.\
                        get_field(field_name)
                    field['operators'] = cls._get_operators_for_field_type(
                        field_object)
                    field['type'] = field_object.__class__.__name__
                    if field_object.choices:
                        field['choices'] = [unicode(x) for x in dict(
                            field_object.choices).values()]

                    condition_choice['fields'][field_name] = field

            condition_choices[content_type.id] = condition_choice
            condition_choices['date_format'] = settings.\
                DATETIME_INPUT_FORMATS[0]

        return condition_choices

    @classmethod
    def get_similar_job_content_types(cls):
        # Create a dict with all available content types.

        available_content_types = {}
        for model in [TestJob, NamedTestAttribute]:
            content_type = ContentType.objects.get_for_model(model)
            available_content_types[content_type.id] = content_type.name
        return available_content_types

    @classmethod
    def _get_operators_for_field_type(cls, field_object):
        # Determine available operators depending on the field type.
        operator_dict = dict(cls.OPERATOR_CHOICES)

        if field_object.choices:
            operator_keys = [
                cls.EXACT,
                cls.NOTEQUAL,
                cls.ICONTAINS
            ]
        elif isinstance(field_object, models.DateTimeField):
            operator_keys = [cls.GT]
        elif isinstance(field_object, models.ForeignKey):
            operator_keys = [
                cls.EXACT,
                cls.IEXACT,
                cls.NOTEQUAL,
                cls.ICONTAINS
            ]
        elif isinstance(field_object, models.BooleanField):
            operator_keys = [
                cls.EXACT,
                cls.NOTEQUAL
            ]
        elif isinstance(field_object, models.IntegerField):
            operator_keys = [
                cls.EXACT,
                cls.NOTEQUAL,
                cls.ICONTAINS,
                cls.GT,
                cls.LT
            ]
        elif isinstance(field_object, models.CharField):
            operator_keys = [
                cls.EXACT,
                cls.IEXACT,
                cls.NOTEQUAL,
                cls.ICONTAINS
            ]
        elif isinstance(field_object, models.TextField):
            operator_keys = [
                cls.EXACT,
                cls.IEXACT,
                cls.NOTEQUAL,
                cls.ICONTAINS
            ]
        else:  # Show all.
            operator_keys = [
                cls.EXACT,
                cls.IEXACT,
                cls.NOTEQUAL,
                cls.ICONTAINS,
                cls.GT,
                cls.LT
            ]

        operators = dict([(i, operator_dict[i]) for i in operator_keys if i in operator_dict])

        return operators


def _get_foreign_key_model(model, fieldname):
    """ Returns model if field is a foreign key, otherwise None. """
    # FIXME: RemovedInDjango110Warning: 'get_field_by_name is an unofficial API
    # that has been deprecated. You may be able to replace it with 'get_field()'
    field_object, model, direct, m2m = model._meta.get_field_by_name(fieldname)
    if not m2m and direct and isinstance(field_object, models.ForeignKey):
        return field_object.rel.to
    return None


class QueryOmitResult(models.Model):

    query = models.ForeignKey(
        Query,
        on_delete=models.CASCADE
    )

    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = fields.GenericForeignKey('content_type', 'object_id')

    class Meta:
        unique_together = (('object_id', 'query', 'content_type'))


class ChartGroup(models.Model):

    name = models.SlugField(max_length=1024, unique=True)

    def __unicode__(self):
        return self.name


# Chart types
CHART_TYPES = ((r'pass/fail', 'Pass/Fail'),
               (r'measurement', 'Measurement'),
               (r'attributes', 'Attributes'))
# Chart representation
REPRESENTATION_TYPES = ((r'lines', 'Lines'),
                        (r'bars', 'Bars'))
# Chart visibility
CHART_VISIBILITY = ((r'chart', 'Chart only'),
                    (r'table', 'Result table only'),
                    (r'both', 'Both'))


class Chart(models.Model):

    name = models.SlugField(max_length=1024, unique=True)

    chart_group = models.ForeignKey(
        ChartGroup,
        default=None,
        null=True,
        on_delete=models.CASCADE)

    owner = models.ForeignKey(
        User,
        default=None,
        on_delete=models.CASCADE)

    group = models.ForeignKey(
        Group,
        default=None,
        null=True,
        on_delete=models.SET_NULL)

    description = models.TextField(blank=True, null=True)

    is_published = models.BooleanField(
        default=False,
        verbose_name='Published')

    queries = models.ManyToManyField(Query, through='ChartQuery', blank=True)

    def __unicode__(self):
        return self.name

    @models.permalink
    def get_absolute_url(self):
        return ("lava.results.chart_display",
                (), dict(name=self.name))

    def can_admin(self, user):
        return user.is_superuser or self.owner == user or \
            (self.group and user in self.group.user_set.all())


# Chart types
CHART_TYPES = ((r'pass/fail', 'Pass/Fail'),
               (r'measurement', 'Measurement'),
               (r'attributes', 'Attributes'))
# Chart representation
REPRESENTATION_TYPES = ((r'lines', 'Lines'),
                        (r'bars', 'Bars'))
# Chart visibility
CHART_VISIBILITY = ((r'chart', 'Chart only'),
                    (r'table', 'Result table only'),
                    (r'both', 'Both'))


class ChartQuery(models.Model):

    class Meta:
        ordering = ['relative_index']

    chart = models.ForeignKey(
        Chart,
        on_delete=models.CASCADE)

    query = models.ForeignKey(
        Query,
        on_delete=models.CASCADE)

    chart_type = models.CharField(
        max_length=20,
        choices=CHART_TYPES,
        verbose_name='Chart type',
        blank=False,
        default="pass/fail",
    )

    target_goal = models.DecimalField(
        blank=True,
        decimal_places=5,
        max_digits=10,
        null=True,
        verbose_name='Target goal')

    chart_height = models.PositiveIntegerField(
        default=300,
        validators=[
            MinValueValidator(200),
            MaxValueValidator(400)
        ],
        verbose_name='Chart height')

    is_percentage = models.BooleanField(
        default=False,
        verbose_name='Percentage')

    chart_visibility = models.CharField(
        max_length=20,
        choices=CHART_VISIBILITY,
        verbose_name='Chart visibility',
        blank=False,
        default="chart",
    )

    xaxis_attribute = models.CharField(
        blank=True,
        null=True,
        max_length=20,
        verbose_name='X-axis attribute')

    representation = models.CharField(
        max_length=20,
        choices=REPRESENTATION_TYPES,
        verbose_name='Representation',
        blank=False,
        default="lines",
    )

    relative_index = models.PositiveIntegerField(
        default=0,
        verbose_name='Order in the chart')

    attributes = models.CharField(
        blank=True,
        null=True,
        max_length=200,
        verbose_name='Chart attributes')

    ORDER_BY_MAP = {
        TestJob: 'end_time',
        TestCase: 'logged',
        TestSuite: 'job__end_time',
    }

    DATE_FORMAT = "%d/%m/%Y %H:%M"

    def get_data(self, user, content_type=None, conditions=None):
        """
        Pack data from filter to json format based on Chart options.

        content_type and conditions are only mandatory if this is a custom
        Chart.
        """

        chart_data = {}
        chart_data["basic"] = self.get_basic_chart_data()
        chart_data["user"] = self.get_user_chart_data(user)

        # TODO: order by attribute if attribute is used for x-axis.
        if hasattr(self, "query"):
            results = self.query.get_results(user).order_by(
                self.ORDER_BY_MAP[self.query.content_type.model_class()])
        # TODO: order by attribute if attribute is used for x-axis.
        else:
            results = Query.get_queryset(
                content_type,
                conditions).visible_by_user(user).order_by(
                    self.ORDER_BY_MAP[content_type.model_class()])

        if self.chart_type == "pass/fail":
            chart_data["data"] = self.get_chart_passfail_data(user, results)

        elif self.chart_type == "measurement":
            # TODO: In case of job or suite, do avg measurement, and later add
            # option to do min/max/other.
            chart_data["data"] = self.get_chart_measurement_data(user, results)

        elif self.chart_type == "attributes":
            chart_data["data"] = self.get_chart_attributes_data(user, results)

        return chart_data

    def get_basic_chart_data(self):
        data = {}
        fields = ["id", "chart_type", "target_goal", "chart_height",
                  "is_percentage", "chart_visibility", "xaxis_attribute",
                  "representation"]

        for field in fields:
            data[field] = getattr(self, field)

        data["chart_name"] = self.chart.name
        if hasattr(self, "query"):
            data["query_name"] = self.query.name
            data["query_link"] = self.query.get_absolute_url()
            data["query_description"] = self.query.description
            data["query_live"] = self.query.is_live
            if self.query.last_updated is not None:
                data["query_updated"] = self.query.last_updated.strftime(
                    settings.DATETIME_INPUT_FORMATS[0])
            data["entity"] = self.query.content_type.model
            data["conditions"] = Query.serialize_conditions(
                self.query.querycondition_set.all())
            data["has_omitted"] = QueryOmitResult.objects.filter(
                query=self.query).exists()

        return data

    def get_user_chart_data(self, user):

        data = {}
        try:
            chart_user = ChartQueryUser.objects.get(
                chart_query=self,
                user=user)
            data["start_date"] = chart_user.start_date
            data["is_legend_visible"] = chart_user.is_legend_visible
            data["is_delta"] = chart_user.is_delta

        except ChartQueryUser.DoesNotExist:
            # Leave an empty dict.
            pass

        return data

    def get_chart_passfail_data(self, user, query_results):

        data = []
        for item in query_results:

            # Set attribute based on xaxis_attribute.
            attribute = item.get_xaxis_attribute(self.xaxis_attribute)
            # If xaxis attribute is set and this query item does not have
            # this specific attribute, ignore it.
            if self.xaxis_attribute and not attribute:
                continue

            date = str(item.get_end_datetime())
            attribute = attribute if attribute is not None else date

            passfail_results = item.get_passfail_results()
            for result in passfail_results:

                if result:
                    chart_item = {
                        "id": result,
                        "pk": item.id,
                        "link": item.get_absolute_url(),
                        "date": date,
                        "attribute": attribute,
                        "pass": passfail_results[result]['fail'] == 0,
                        "passes": passfail_results[result]['pass'],
                        "failures": passfail_results[result]['fail'],
                        "skip": passfail_results[result]['skip'],
                        "unknown": passfail_results[result]['unknown'],
                        "total": (passfail_results[result]['pass'] +
                                  passfail_results[result]['fail'] +
                                  passfail_results[result]['unknown'] +
                                  passfail_results[result]['skip']),
                    }
                    data.append(chart_item)

        return data

    def get_chart_measurement_data(self, user, query_results):

        data = []
        for item in query_results:

            # Set attribute based on xaxis_attribute.
            attribute = item.get_xaxis_attribute(self.xaxis_attribute)
            # If xaxis attribute is set and this query item does not have
            # this specific attribute, ignore it.
            if self.xaxis_attribute and not attribute:
                continue

            date = str(item.get_end_datetime())
            attribute = attribute if attribute is not None else date

            measurement_results = item.get_measurement_results()
            for result in measurement_results:

                if result:
                    chart_item = {
                        "id": result,
                        "pk": item.id,
                        "link": item.get_absolute_url(),
                        "date": date,
                        "attribute": attribute,
                        "pass": measurement_results[result]['fail'] == 0,
                        "measurement": measurement_results[result]['measurement']
                    }
                data.append(chart_item)

        return data

    def get_chart_attributes_data(self, user, query_results):

        data = []
        for item in query_results:

            attribute_results = item.get_attribute_results(self.attributes)
            for result in attribute_results:
                if result:
                    chart_item = {
                        "id": result,
                        "pk": item.id,
                        "attribute": str(item.get_end_datetime()),
                        "link": item.get_absolute_url(),
                        "date": str(item.get_end_datetime()),
                        "pass": attribute_results[result]['fail'] == 0,
                        "attr_value": attribute_results[result]['value'],
                    }
                data.append(chart_item)

        return data

    def __unicode__(self):
        return self.name

    @models.permalink
    def get_absolute_url(self):
        return ("lava.results.chart_query_edit",
                (), dict(name=self.chart.name, id=self.id))


class ChartQueryUser(models.Model):

    class Meta:
        unique_together = ("chart_query", "user")

    chart_query = models.ForeignKey(
        ChartQuery,
        null=False,
        on_delete=models.CASCADE)

    user = models.ForeignKey(
        User,
        null=False,
        on_delete=models.CASCADE)

    # Start date can actually also be start build number, ergo char, not date.
    # Also, we do not store end date(build number) since user's only want
    # to see the latest data.
    start_date = models.CharField(max_length=20)

    is_legend_visible = models.BooleanField(
        default=True,
        verbose_name='Toggle legend')

    is_delta = models.BooleanField(
        default=False,
        verbose_name='Delta reporting')
