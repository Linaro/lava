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

import json

from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core import serializers
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.urlresolvers import reverse
from django.http import Http404
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.db.models import Q
from lava_server.bread_crumbs import (
    BreadCrumb,
    BreadCrumbTrail,
)
from dashboard_app.filters import (
    evaluate_filter,
)
from django_tables2 import (
    RequestConfig,
)

from dashboard_app.models import (
    Bundle,
    BundleStream,
    NamedAttribute,
    Test,
    TestCase,
    TestRun,
    TestRunFilter,
    TestRunFilterSubscription,
)
from dashboard_app.views import (
    index,
)
from dashboard_app.views.filters.forms import (
    TestRunFilterForm,
    TestRunFilterSubscriptionForm,
)
from dashboard_app.views.filters.tables import (
    FilterSummaryTable,
    FilterPassTable,
    PublicFiltersTable,
    TestResultDifferenceTable,
    UserFiltersTable,
)
from lava.utils.lavatable import LavaView


class FilterView(LavaView):

    def __init__(self, request, **kwargs):
        super(FilterView, self).__init__(request, **kwargs)

    def stream_query(self, term):
        streams = BundleStream.objects.filter(pathname__contains=term)
        return Q(bundle_streams__in=streams)


class UserFiltersView(FilterView):

    def get_queryset(self):
        return TestRunFilter.objects.filter(owner=self.request.user)


class PublicFiltersView(FilterView):

    def get_queryset(self):
        return TestRunFilter.objects.filter(public=True)


@BreadCrumb("Filters and Subscriptions", parent=index)
def filters_list(request):
    public_view = PublicFiltersView(request, model=TestRunFilter, table_class=PublicFiltersTable)
    prefix = "public_"
    public_filters_table = PublicFiltersTable(
        public_view.get_table_data(prefix),
        prefix=prefix
    )
    config = RequestConfig(request)
    config.configure(public_filters_table)

    search_data = public_filters_table.prepare_search_data(public_view)
    discrete_data = public_filters_table.prepare_discrete_data(public_view)
    terms_data = public_filters_table.prepare_terms_data(public_view)
    times_data = public_filters_table.prepare_times_data(public_view)

    user_filters_table = None
    if request.user.is_authenticated():
        user_view = UserFiltersView(request, model=TestRunFilter, table_class=UserFiltersTable)
        prefix = "user_"
        user_filters_table = UserFiltersTable(
            user_view.get_table_data(prefix),
            prefix=prefix
        )
        config.configure(user_filters_table)
        search_data.update(user_filters_table.prepare_search_data(user_view))
        discrete_data.update(user_filters_table.prepare_discrete_data(user_view))
        terms_data.update(user_filters_table.prepare_terms_data(user_view))

    return render_to_response(
        'dashboard_app/filters_list.html', {
            'user_filters_table': user_filters_table,
            'public_filters_table': public_filters_table,
            "terms_data": terms_data,
            "search_data": search_data,
            "times_data": times_data,
            "discrete_data": discrete_data,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                filters_list),
        }, RequestContext(request)
    )


def filter_name_list_json(request):

    term = request.GET['term']
    filters = []
    for filter in TestRunFilter.objects.filter(Q(name__istartswith=term) |
                                               Q(owner__username__istartswith=term)):
        filters.append(
            {"id": filter.id,
             "name": filter.name,
             "label": filter.owner_name})
    return HttpResponse(json.dumps(filters), content_type='application/json')


class FilterDetailView(LavaView):

    def __init__(self, request, filter_object, **kwargs):
        super(FilterDetailView, self).__init__(request, **kwargs)
        self.filter_object = filter_object
        self.match_maker = None

    def get_queryset(self):
        return self.match_maker.queryset

    def is_pass_table(self):
        if not self.match_maker:
            self.match_maker = evaluate_filter(self.request.user, self.filter_object.as_data())
        if self.match_maker.filter_data['tests']:
            self.table_class = FilterPassTable
            return True
        self.table_class = FilterSummaryTable
        return False


@BreadCrumb("Filter ~{username}/{name}", parent=filters_list, needs=['username', 'name'])
def filter_detail(request, username, name):
    qfilter = get_object_or_404(TestRunFilter, owner__username=username, name=name)
    if not request.user.is_superuser:
        if not qfilter.public and qfilter.owner != request.user:
            raise PermissionDenied()
    if not request.user.is_authenticated():
        subscription = None
    else:
        try:
            subscription = TestRunFilterSubscription.objects.get(
                user=request.user, filter=qfilter)
        except TestRunFilterSubscription.DoesNotExist:
            subscription = None
    view = FilterDetailView(request, qfilter, model=TestRun)
    if view.is_pass_table():
        table = FilterPassTable(view.get_table_data(), match_maker=view.match_maker)
    else:
        table = FilterSummaryTable(view.get_table_data(), match_maker=view.match_maker)
    RequestConfig(request, paginate={"per_page": table.length}).configure(table)
    return render_to_response(
        'dashboard_app/filter_detail.html', {
            'filter': qfilter,
            'subscription': subscription,
            'filter_table': table,
            "terms_data": table.prepare_terms_data(view),
            "search_data": table.prepare_search_data(view),
            "discrete_data": table.prepare_discrete_data(view),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                filter_detail, name=name, username=username),
        }, RequestContext(request)
    )


@BreadCrumb("Manage Subscription", parent=filter_detail, needs=['username', 'name'])
@login_required
def filter_subscribe(request, username, name):
    filter = get_object_or_404(TestRunFilter, owner__username=username, name=name)
    if not request.user.is_superuser:
        if not filter.public and filter.owner != request.user:
            raise PermissionDenied()
    try:
        subscription = TestRunFilterSubscription.objects.get(
            user=request.user, filter=filter)
    except TestRunFilterSubscription.DoesNotExist:
        subscription = None
    if request.method == "POST":
        form = TestRunFilterSubscriptionForm(
            filter, request.user, request.POST, instance=subscription)
        if form.is_valid():
            if 'unsubscribe' in request.POST:
                subscription.delete()
            else:
                form.save()
            return HttpResponseRedirect(filter.get_absolute_url())
    else:
        form = TestRunFilterSubscriptionForm(
            filter, request.user, instance=subscription)
    return render_to_response(
        'dashboard_app/filter_subscribe.html', {
            'filter': filter,
            'form': form,
            'subscription': subscription,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                filter_subscribe, name=name, username=username),
        }, RequestContext(request)
    )


def filter_form(request, bread_crumb_trail, instance=None, is_copy=False):
    if request.method == 'POST':
        if instance:
            owner = instance.owner
        else:
            owner = request.user
        form = TestRunFilterForm(owner, request.POST, instance=instance,
                                 is_copy=is_copy)

        if form.is_valid():
            if 'save' in request.POST:
                qfilter = form.save()
                return HttpResponseRedirect(qfilter.get_absolute_url())
            else:
                c = request.POST.copy()
                c.pop('csrfmiddlewaretoken', None)
                view = FilterDetailView(request, form, model=TestRun)
                if view.is_pass_table():
                    table = FilterPassTable(view.get_table_data(), match_maker=view.match_maker)
                else:
                    table = FilterSummaryTable(view.get_table_data(), match_maker=view.match_maker)
                RequestConfig(request, paginate={"per_page": table.length}).configure(table)
                return render_to_response(
                    'dashboard_app/filter_preview.html', {
                        'bread_crumb_trail': bread_crumb_trail,
                        'form': form,
                        'table': table,
                    }, RequestContext(request))
    else:
        form = TestRunFilterForm(request.user, instance=instance,
                                 is_copy=is_copy)

    filter_name = None
    if is_copy:
        filter_name = instance.name
        instance.name = None

    return render_to_response(
        'dashboard_app/filter_add.html', {
            'bread_crumb_trail': bread_crumb_trail,
            'form': form,
            'is_copy': is_copy,
            'filter_name': filter_name,
        }, RequestContext(request))


@BreadCrumb("Add new filter", parent=filters_list)
@login_required
def filter_add(request):
    return filter_form(
        request,
        BreadCrumbTrail.leading_to(filter_add))


@BreadCrumb("Edit", parent=filter_detail, needs=['username', 'name'])
def filter_edit(request, username, name):
    if not request.user.is_superuser:
        if request.user.username != username:
            raise PermissionDenied()
    filter = get_object_or_404(TestRunFilter, owner__username=username, name=name)
    return filter_form(
        request,
        BreadCrumbTrail.leading_to(filter_edit, name=name, username=username),
        instance=filter)


@BreadCrumb("Copy", parent=filter_detail, needs=['username', 'name'])
@login_required
def filter_copy(request, username, name):
    filter = get_object_or_404(TestRunFilter, owner__username=username, name=name)
    if not request.user.is_superuser:
        if not filter.public and filter.owner != request.user:
            raise PermissionDenied()

    return filter_form(
        request,
        BreadCrumbTrail.leading_to(filter_copy, name=name, username=username),
        instance=filter,
        is_copy=True)


@BreadCrumb("Delete", parent=filter_detail, needs=['username', 'name'])
def filter_delete(request, username, name):
    if not request.user.is_superuser:
        if request.user.username != username:
            raise PermissionDenied()
    filter = get_object_or_404(TestRunFilter, owner__username=username, name=name)
    if request.method == "POST":
        if 'yes' in request.POST:
            filter.delete()
            return HttpResponseRedirect(reverse(filters_list))
        else:
            return HttpResponseRedirect(filter.get_absolute_url())
    return render_to_response(
        'dashboard_app/filter_delete.html', {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(filter_delete, name=name, username=username),
            'filter': filter,
        }, RequestContext(request))


def filter_add_cases_for_test_json(request):
    if not request.GET.get('test', None):
        raise Http404

    test = get_object_or_404(Test, test_id=request.GET['test'])
    result = TestCase.objects.filter(test=test).order_by('test_case_id').values('test_case_id', 'id')
    return HttpResponse(
        json.dumps(list(result)),
        content_type='application/json')


def get_tests_json(request):
    if not request.GET.get('id', None):
        raise Http404

    tests = Test.objects.filter(
        test_runs__bundle__bundle_stream__testrunfilter__id=request.GET['id']).distinct('test_id').order_by('test_id')

    data = serializers.serialize('json', tests)
    return HttpResponse(data, content_type='application/json')


def get_test_cases_json(request):
    if not request.GET.get('test_id', None) or not request.GET.get('id', None):
        raise Http404

    test_cases = TestCase.objects.filter(
        test__test_runs__bundle__bundle_stream__testrunfilter__id=request.GET['id'],
        test__id=request.GET['test_id']).exclude(units__exact='').distinct('test_case_id').order_by('test_case_id')

    data = serializers.serialize('json', test_cases)
    return HttpResponse(data, content_type='application/json')


def filter_attr_name_completion_json(request):
    term = request.GET['term']
    content_type_id = ContentType.objects.get_for_model(TestRun).id
    result = NamedAttribute.objects.filter(
        name__startswith=term,
        content_type_id=content_type_id).distinct().order_by('name').values_list('name', flat=True)
    return HttpResponse(
        json.dumps(list(result)),
        content_type='application/json')


def filter_attr_value_completion_json(request):
    name = request.GET['name']
    term = request.GET['term']
    content_type_id = ContentType.objects.get_for_model(TestRun).id
    result = NamedAttribute.objects.filter(
        name=name, content_type_id=content_type_id,
        value__startswith=term).distinct().order_by('value').values_list('value', flat=True)
    return HttpResponse(
        json.dumps(list(result)),
        content_type='application/json')


def _iter_matching(seq1, seq2, key):
    """Iterate over sequences in the order given by the key function, matching
    elements with matching key values.

    For example:

    >>> seq1 = [(1, 2), (2, 3)]
    >>> seq2 = [(1, 3), (3, 4)]
    >>> def key(pair): return pair[0]
    >>> list(_iter_matching(seq1, seq2, key))
    [(1, (1, 2), (1, 3)), (2, (2, 3), None), (3, None, (3, 4))]
    """
    seq1.sort(key=key)
    seq2.sort(key=key)
    sentinel = object()

    def next(it):
        try:
            o = it.next()
            return (key(o), o)
        except StopIteration:
            return (sentinel, None)
    iter1 = iter(seq1)
    iter2 = iter(seq2)
    k1, o1 = next(iter1)
    k2, o2 = next(iter2)
    while k1 is not sentinel or k2 is not sentinel:
        if k1 is sentinel:
            yield (k2, None, o2)
            k2, o2 = next(iter2)
        elif k2 is sentinel:
            yield (k1, o1, None)
            k1, o1 = next(iter1)
        elif k1 == k2:
            yield (k1, o1, o2)
            k1, o1 = next(iter1)
            k2, o2 = next(iter2)
        elif k1 < k2:
            yield (k1, o1, None)
            k1, o1 = next(iter1)
        else:  # so k1 > k2...
            yield (k2, None, o2)
            k2, o2 = next(iter2)


def _test_run_difference(test_run1, test_run2, cases=None):
    test_results1 = list(test_run1.test_results.all().select_related('test_case'))
    test_results2 = list(test_run2.test_results.all().select_related('test_case'))

    def key(tr):
        return tr.test_case.test_case_id
    differences = []
    for tc_id, tc1, tc2 in _iter_matching(test_results1, test_results2, key):
        if cases is not None and tc_id not in cases:
            continue
        if tc1:
            tc1 = tc1.result_code
        if tc2:
            tc2 = tc2.result_code
        if tc1 != tc2:
            differences.append({
                'test_case_id': tc_id,
                'first_result': tc1,
                'second_result': tc2,
            })
    return differences


def compare_filter_matches(request, filter_data, tag1, tag2):
    matches = evaluate_filter(request.user, filter_data)
    match1, match2 = matches.with_tags(tag1, tag2)
    test_cases_for_test_id = {}
    for test in filter_data['tests']:
        test_cases = test['test_cases']
        if test_cases:
            test_cases = set([tc.test_case_id for tc in test_cases])
        else:
            test_cases = None
        test_cases_for_test_id[test['test'].test_id] = test_cases
    test_run_info = []

    def key(tr):
        return tr.test.test_id
    for key, tr1, tr2 in _iter_matching(match1.test_runs, match2.test_runs, key):
        if tr1 is None:
            table = None
            only = 'right'
            tr = tr2
            tag = tag2
            cases = None
        elif tr2 is None:
            table = None
            only = 'left'
            tr = tr1
            tag = tag1
            cases = None
        else:
            only = None
            tr = None
            tag = None
            cases = test_cases_for_test_id.get(key)
            test_result_differences = _test_run_difference(tr1, tr2, cases)
            if test_result_differences:
                table = TestResultDifferenceTable(test_result_differences, prefix=key)
                table.base_columns['first_result'].verbose_name = mark_safe(
                    '<a href="%s">build %s: %s</a>' % (
                        tr1.get_absolute_url(), escape(tag1), escape(key)))
                table.base_columns['second_result'].verbose_name = mark_safe(
                    '<a href="%s">build %s: %s</a>' % (
                        tr2.get_absolute_url(), escape(tag2), escape(key)))
                RequestConfig(request, paginate={"per_page": table.length}).configure(table)
            else:
                table = None
            if cases:
                cases = sorted(cases)
                if len(cases) > 1:
                    cases = ', '.join(cases[:-1]) + ' or ' + cases[-1]
                else:
                    cases = cases[0]
        test_run_info.append(dict(
            only=only,
            key=key,
            table=table,
            tr=tr,
            tag=tag,
            cases=cases))
    return test_run_info


@BreadCrumb(
    "Comparing builds {tag1} and {tag2}",
    parent=filter_detail,
    needs=['username', 'name', 'tag1', 'tag2'])
def compare_matches(request, username, name, tag1, tag2):
    filter = get_object_or_404(TestRunFilter, owner__username=username, name=name)
    if not request.user.is_superuser:
        if not filter.public and filter.owner != request.user:
            raise PermissionDenied()
    filter_data = filter.as_data()
    test_run_info = compare_filter_matches(request, filter_data, tag1, tag2)
    return render_to_response(
        "dashboard_app/filter_compare_matches.html", {
            'test_run_info': test_run_info,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                compare_matches,
                name=name,
                username=username,
                tag1=tag1,
                tag2=tag2),
        }, RequestContext(request))
