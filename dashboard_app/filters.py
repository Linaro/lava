
# A test run filter allows a user to produce an ordered list of results of
# interest.

# The data that makes up a filter are:
#
# * A non-empty set of bundle streams
# * A possibly empty set of (attribute-name, attribute-value) pairs
# * A possibly empty list of tests, each of which has a possibly empty list of
#   test cases
# * An optional build number attribute name

# A filter matches a test run if:
#
# * It is part of a bundle that is in one of the specified streams
# * It has all the attribute names with the specified values (or there are no
#   attributes specified)
# * The test of the test run is one of those specified (or there are no test
#   runs specified)
# * One of the results of the test run is one of those specified (or there are
#   no test cases specified)
# * The build number attribute is present, if specified.
#
# The test runs matching a filter are grouped, either by the upload date of
# the bundle or by the value of the build number attribute.

# We define several representations for this data:
#
# * One is the TestRunFilter and related tables (the "model represenation").
#   These have some representation specific metadata that does not relate to
#   the test runs the filter selects: names, owner, the "public" flag.

# * One is the natural Python data structure for the data (the "in-memory
#   representation"), i.e.
#     {
#         bundle_streams: [<BundleStream objects>],
#         attributes: [(attr-name, attr-value)],
#         tests: [{"test": <Test instance>, "test_cases":[<TestCase instances>]}],
#         build_number_attribute: attr-name-or-None,
#         uploaded_by: <User instance-or-None>,
#     }
#   This is the representation that is used to evaluate a filter (so that
#   previewing new filters can be done without having to create a
#   TestRunFilter instance that we carefully don't save to the database --
#   which doesn't work very well anyway with all the ManyToMany relations
#   involved)

# * The final one is the TRFForm object defined in
#   dashboard_app.views.filters.forms (the "form representation")
#   (pedantically, the rendered form of this is yet another
#   representation...).  This representation is the only one other than the
#   model objects to include the name/owner/public metadata.

# evaluate_filter returns a sort of fake QuerySet.  Iterating over it returns
# "FilterMatch" objects, whose attributes are described in the class
# defintion.  A FilterMatch also has a serializable representation:
#
# {
#       'tag': either a stringified date (bundle__uploaded_on) or a build number
#       'test_runs': [{
#           'test_id': test_id
#           'link': link-to-test-run,
#           'passes': int, 'fails': int, 'skips': int, 'total': int,
#           # only present if filter specifies cases for this test:
#           'specific_results': [{
#               'test_case_id': test_case_id,
#               'link': link-to-test-result,
#               'result': pass/fail/skip/unknown,
#               'measurement': string-containing-decimal-or-None,
#               'units': units,
#               }],
#           }]
#       # Only present if filter does not specify tests:
#       'pass_count': int,
#       'fail_count': int,
# }

import datetime

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.db.models.sql.aggregates import Aggregate as SQLAggregate

from dashboard_app.models import (
    BundleStream,
    NamedAttribute,
    TestResult,
    TestRun,
)


class FilterMatch(object):
    """A non-database object that represents the way a filter matches a test_run.

    Returned by TestRunFilter.matches_against_bundle and evaluate_filter.
    """

    # filter is the model representation of the filter (this is only set
    # by matches_against_bundle)
    filter = None
    filter_data = None  # The in-memory representation of the filter.
    tag = None  # either a date (bundle__uploaded_on) or a build number

    # test_runs will be all test runs from the bundle if
    # filter_data['tests'] is empty, will just be the test
    # runs with matching tests if not.
    test_runs = None

    specific_results = None  # Will stay none unless filter specifies a test case

    pass_count = None  # Only filled out for filters that dont specify a test
    result_count = None  # Ditto

    def serializable(self, include_links=True):
        cases_by_test = {}
        for test in self.filter_data['tests']:
            # Not right if filter specifies a test more than once...
            if test['test_cases']:
                cases_by_test[test['test']] = test['test_cases']
        test_runs = []

        domain = '???'
        try:
            site = Site.objects.get_current()
        except (Site.DoesNotExist, ImproperlyConfigured):
            pass
        else:
            domain = site.domain
        url_prefix = 'http://%s' % domain

        for tr in self.test_runs:
            d = {
                'test_id': tr.test.test_id,
                'pass': 0,
                'fail': 0,
                'skip': 0,
                'unknown': 0,
                'total': 0,
            }
            if include_links:
                d['link'] = url_prefix + tr.get_absolute_url()
            if tr.test in cases_by_test:
                results = d['specific_results'] = []
                for result in self.specific_results:
                    if result.test_run == tr:
                        result_str = TestResult.RESULT_MAP[result.result]
                        result_data = {
                            'test_case_id': result.test_case.test_case_id,
                            'result': result_str,
                        }
                        if include_links:
                            result_data['link'] = url_prefix + result.get_absolute_url()
                        if result.measurement is not None:
                            result_data['measurement'] = str(result.measurement)
                        if result.units is not None:
                            result_data['units'] = str(result.units)
                        results.append(result_data)
                        d[result_str] += 1
                        d['total'] += 1
            else:
                d['pass'] = tr.denormalization.count_pass
                d['fail'] = tr.denormalization.count_fail
                d['skip'] = tr.denormalization.count_skip
                d['unknown'] = tr.denormalization.count_unknown
                d['total'] = tr.denormalization.count_all()
            test_runs.append(d)
        r = {
            'tag': str(self.tag),
            'test_runs': test_runs,
        }
        if self.pass_count is not None:
            r['pass_count'] = self.pass_count
        if self.result_count is not None:
            r['result_count'] = self.result_count
        return r

    def _format_test_result(self, result):
        prefix = result.test_case.test.test_id + ':' + result.test_case.test_case_id + ' '
        if result.test_case.units:
            return prefix + '%s%s' % (result.measurement, result.units)
        else:
            return prefix + result.RESULT_MAP[result.result]

    def _format_test_run(self, tr):
        return "%s %s pass / %s total" % (
            tr.test.test_id,
            tr.denormalization.count_pass,
            tr.denormalization.count_all())

    def _format_many_test_runs(self):
        return "%s pass / %s total" % (self.pass_count, self.result_count)

    def format_for_mail(self):
        r = [' ~%s/%s ' % (self.filter.owner.username, self.filter.name)]
        if not self.filter_data['tests']:
            r.append(self._format_many_test_runs())
        else:
            for test in self.filter_data['tests']:
                if not test['test_cases']:
                    for tr in self.test_runs:
                        if tr.test == test.test:
                            r.append('\n    ')
                            r.append(self._format_test_run(tr))
                for test_case in test['test_cases']:
                    for result in self.specific_results:
                        if result.test_case.id == test_case.id:
                            r.append('\n    ')
                            r.append(self._format_test_result(result))
        r.append('\n')
        return ''.join(r)


class MatchMakingQuerySet(object):
    """Wrap a QuerySet and construct FilterMatchs from what the wrapped query
    set returns.

    Just enough of the QuerySet API to work with Django Tables (i.e. pretend
    ordering and real slicing)."""

    model = TestRun

    def __init__(self, queryset, filter_data, prefetch_related):
        self.queryset = queryset
        self.filter_data = filter_data
        self.prefetch_related = prefetch_related
        if filter_data.get('build_number_attribute'):
            self.key = 'build_number'
            self.key_name = 'Build'
        else:
            self.key = 'bundle__uploaded_on'
            self.key_name = 'Uploaded On'

    def _makeMatches(self, data):
        test_run_ids = set()
        for datum in data:
            test_run_ids.update(datum['id__arrayagg'])
        r = []
        trs = TestRun.objects.filter(id__in=test_run_ids)\
            .select_related('denormalization',
                            'bundle',
                            'bundle__bundle_stream',
                            'test')\
            .prefetch_related(*self.prefetch_related)
        trs_by_id = {}
        for tr in trs:
            trs_by_id[tr.id] = tr
        case_ids = set()
        for t in self.filter_data['tests']:
            for case in t['test_cases']:
                case_ids.add(case.id)
        if case_ids:
            result_ids_by_tr_id = {}
            results_by_tr_id = {}
            values = TestResult.objects.filter(
                test_case__id__in=case_ids,
                test_run__id__in=test_run_ids).values_list('test_run__id', 'id')
            result_ids = set()
            for v in values:
                result_ids_by_tr_id.setdefault(v[0], []).append(v[1])
                result_ids.add(v[1])

            results_by_id = {}
            prefetch = self.prefetch_related
            if "test_results" in prefetch:
                prefetch.remove("test_results")
            for result in TestResult.objects.filter(
                    id__in=list(result_ids)).select_related(
                    'test_run__test', 'test_case', 'test_run__bundle__bundle_stream').prefetch_related(*prefetch):
                results_by_id[result.id] = result

            for tr_id, result_ids in result_ids_by_tr_id.items():
                rs = results_by_tr_id[tr_id] = []
                for result_id in result_ids:
                    rs.append(results_by_id[result_id])
        for datum in data:
            trs = []
            for tr_id in set(datum['id__arrayagg']):
                trs.append(trs_by_id[tr_id])
            match = FilterMatch()
            match.test_runs = trs
            match.filter_data = self.filter_data
            match.tag = datum[self.key]
            if case_ids:
                match.specific_results = []
                for tr_id in set(datum['id__arrayagg']):
                    match.specific_results.extend(results_by_tr_id.get(tr_id, []))
            else:
                match.pass_count = sum(tr.denormalization.count_pass for tr in trs)
                match.result_count = sum(tr.denormalization.count_all() for tr in trs)
            r.append(match)
        return iter(r)

    def _wrap(self, queryset, **kw):
        return self.__class__(queryset, self.filter_data,
                              self.prefetch_related, **kw)

    def order_by(self, *args):
        # the generic tables code calls this even when it shouldn't...
        return self

    def since(self, since):
        if self.key == 'build_number':
            q = self.queryset.extra(
                where=['convert_to_integer("dashboard_app_namedattribute"."value") > %d' % since]
            )
        else:
            assert isinstance(since, datetime.datetime)
            q = self.queryset.filter(bundle__uploaded_on__gt=since)
        return self._wrap(q)

    def with_tags(self, tag1, tag2):
        if self.key == 'build_number':
            q = self.queryset.extra(
                where=['convert_to_integer("dashboard_app_namedattribute"."value") in (%s, %s)' % (tag1, tag2)]
            )
        else:
            tag1 = datetime.datetime.strptime(tag1, "%Y-%m-%d %H:%M:%S.%f")
            tag2 = datetime.datetime.strptime(tag2, "%Y-%m-%d %H:%M:%S.%f")
            q = self.queryset.filter(bundle__uploaded_on__in=(tag1, tag2))
        matches = list(self._wrap(q))
        if matches[0].tag == tag1:
            return matches
        else:
            matches.reverse()
            return matches

    def count(self):
        return self.queryset.count()

    def __getitem__(self, item):
        return self._wrap(self.queryset[item])

    def __iter__(self):
        data = list(self.queryset)
        return self._makeMatches(data)


class SQLArrayAgg(SQLAggregate):
    sql_function = 'array_agg'


class ArrayAgg(models.Aggregate):
    name = 'ArrayAgg'

    def add_to_query(self, query, alias, col, source, is_summary):
        aggregate = SQLArrayAgg(
            col, source=source, is_summary=is_summary, **self.extra)
        # For way more detail than you want about what this next line is for,
        # see
        # http://voices.canonical.com/michael.hudson/2012/09/02/using-postgres-array_agg-from-django/
        aggregate.field = models.DecimalField()  # vomit
        query.aggregates[alias] = aggregate


# given filter:
# select from testrun
#  where testrun.bundle in filter.bundle_streams ^ accessible_bundles
#    and testrun has attribute with key = key1 and value = value1
#    and testrun has attribute with key = key2 and value = value2
#    and               ...
#    and testrun has attribute with key = keyN and value = valueN
#    and testrun has any of the tests/testcases requested
#    [and testrun has attribute with key = build_number_attribute]
#    [and testrun.bundle.uploaded_by = uploaded_by]
def evaluate_filter(user, filter_data, prefetch_related=[], descending=True):
    accessible_bundle_streams = BundleStream.objects.accessible_by_principal(
        user)
    bs_ids = list(
        accessible_bundle_streams.filter(
            id__in=[bs.id for bs in filter_data['bundle_streams']]).values_list('id', flat=True))
    conditions = [models.Q(bundle__bundle_stream__id__in=bs_ids)]

    content_type_id = ContentType.objects.get_for_model(TestRun).id

    for (name, value) in filter_data['attributes']:
        # We punch through the generic relation abstraction here for 100x
        # better performance.
        conditions.append(
            models.Q(id__in=NamedAttribute.objects.filter(
                name=name, value=value, content_type_id=content_type_id).values('object_id')))
    test_condition = None
    for test in filter_data.get('tests', []):
        case_ids = set()
        for test_case in test.get('test_cases', []):
            case_ids.add(test_case.id)
        if case_ids:
            q = models.Q(
                test__id=test['test'].id,
                test_results__test_case__id__in=case_ids)
        else:
            q = models.Q(test__id=test['test'].id)
        if test_condition:
            test_condition = test_condition | q
        else:
            test_condition = q
    if test_condition:
        conditions.append(test_condition)

    if filter_data.get('uploaded_by'):
        conditions.append(models.Q(bundle__uploaded_by=filter_data['uploaded_by']))

    testruns = TestRun.objects.filter(*conditions)

    if filter_data.get('build_number_attribute'):
        if descending:
            ob = ['-build_number']
        else:
            ob = ['build_number']
        testruns = testruns.filter(
            attributes__name=filter_data['build_number_attribute'])\
            .extra(
                select={'build_number': 'convert_to_integer("dashboard_app_namedattribute"."value")', },
                where=['convert_to_integer("dashboard_app_namedattribute"."value") IS NOT NULL'])\
            .extra(order_by=ob,).values('build_number').annotate(ArrayAgg('id'))
    else:
        if descending:
            ob = '-bundle__uploaded_on'
        else:
            ob = 'bundle__uploaded_on'
        testruns = testruns.order_by(ob).values(
            'bundle__uploaded_on').annotate(ArrayAgg('id'))

    return MatchMakingQuerySet(testruns, filter_data, prefetch_related)


def get_named_attributes(filter, content_type):
    # Returns the list of id's for specific content type objects
    # which are selected by custom attribute in the filter.
    object_attribute_ids = None
    for attr in filter.attributes.all():
        attrs = NamedAttribute.objects.filter(
            name=attr.name, value=attr.value,
            content_type_id=content_type.id).values_list(
                'object_id', flat=True)
        if object_attribute_ids is None:
            object_attribute_ids = set(attrs)
        else:
            object_attribute_ids &= set(attrs)

    return object_attribute_ids


def get_filter_testruns(user, filter, prefetch_related=[], limit=100,
                        descending=True, image_chart_filter=None):
    # Return the list of test runs which meet the conditions specified in the
    # filter.

    testruns = TestRun.objects.filter(
        bundle__bundle_stream__testrunfilter=filter
    )

    test_run_attributes_ids = get_named_attributes(
        filter, ContentType.objects.get_for_model(TestRun))

    if test_run_attributes_ids:
        testruns = testruns.filter(id__in=test_run_attributes_ids)

    # Set to False only if build number attr. is None or empty.
    use_build_number = bool(filter.build_number_attribute)
    if image_chart_filter:
        testruns = testruns.filter(
            test__imagecharttest__image_chart_filter=image_chart_filter)
        use_build_number = image_chart_filter.image_chart.is_build_number and \
            use_build_number
    elif filter.tests.all():
        testruns = testruns.filter(test__testrunfilters__filter=filter)

    if use_build_number:
        if descending:
            ob = ['-build_number']
        else:
            ob = ['build_number']
        testruns = testruns.filter(
            attributes__name=filter.build_number_attribute)\
            .extra(select={'build_number': 'convert_to_integer("dashboard_app_namedattribute"."value")', },
                   where=['convert_to_integer("dashboard_app_namedattribute"."value") IS NOT NULL']).extra(order_by=ob,)
    else:
        if descending:
            ob = '-bundle__uploaded_on'
        else:
            ob = 'bundle__uploaded_on'
        testruns = testruns.order_by(ob)

    testruns = testruns.prefetch_related(
        'denormalization',
        'bundle',
        'bundle__bundle_stream',
        'test'
    )[:limit]

    return reversed(testruns)


def get_filter_testresults(user, filter, prefetch_related=[], limit=50,
                           descending=True, image_chart_filter=None):
    # Return the list of test results which meet the conditions specified in
    # the filter.

    testresults = TestResult.objects.filter(
        test_run__bundle__bundle_stream__testrunfilter=filter
    )

    test_run_attributes_ids = get_named_attributes(
        filter, ContentType.objects.get_for_model(TestRun))

    if test_run_attributes_ids:
        testresults = testresults.filter(
            test_run__id__in=test_run_attributes_ids)

    # Set to False only if build number attr. is None or empty.
    use_build_number = bool(filter.build_number_attribute)
    if image_chart_filter:
        testresults = testresults.filter(
            test_case__imagecharttestcase__image_chart_filter=image_chart_filter)
        use_build_number = image_chart_filter.image_chart.is_build_number and \
            use_build_number
    elif filter.testcases.all():
        testresults = testresults.filter(
            test_case__test__testrunfilters__filter=filter)

    if use_build_number:
        if descending:
            ob = ['-build_number']
        else:
            ob = ['build_number']
        testresults = testresults.filter(
            test_run__attributes__name=filter.build_number_attribute)\
            .extra(select={'build_number': 'convert_to_integer("dashboard_app_namedattribute"."value")', },
                   where=['convert_to_integer("dashboard_app_namedattribute"."value") IS NOT NULL']).extra(order_by=ob,)
    else:
        if descending:
            ob = '-test_run__bundle__uploaded_on'
        else:
            ob = 'test_run__bundle__uploaded_on'
        testresults = testresults.order_by(ob)

    testresults = testresults.prefetch_related(
        'test_run__denormalization',
        'test_run__bundle',
        'test_run__bundle__bundle_stream',
        'test_run__test'
    )[:limit]

    return reversed(testresults)
