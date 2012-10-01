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
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext

from lava_server.bread_crumbs import (
    BreadCrumb,
    BreadCrumbTrail,
)

from dashboard_app.models import (
    NamedAttribute,
    Test,
    TestCase,
    TestRun,
    TestRunFilter,
    TestRunFilterSubscription,
    )
from dashboard_app.views import index
from dashboard_app.views.filters.forms import (
    TestRunFilterForm,
    TestRunFilterSubscriptionForm,
    )
from dashboard_app.views.filters.tables import (
    FilterTable,
    FilterPreviewTable,
    PublicFiltersTable,
    UserFiltersTable,
    )


@BreadCrumb("Filters and Subscriptions", parent=index)
def filters_list(request):
    public_filters_table = PublicFiltersTable("public-filters", None)
    if request.user.is_authenticated():
        public_filters_table.user = request.user
        user_filters_table = UserFiltersTable("user-filters", None, params=(request.user,))
        user_filters_table.user = request.user
    else:
        user_filters_table = None
        del public_filters_table.base_columns['subscription']

    return render_to_response(
        'dashboard_app/filters_list.html', {
            'user_filters_table': user_filters_table,
            'public_filters_table': public_filters_table,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                filters_list),
        }, RequestContext(request)
    )


def filter_json(request, username, name):
    filter = TestRunFilter.objects.get(owner__username=username, name=name)
    return FilterTable.json(request, params=(request.user, filter))



def filter_preview_json(request):
    try:
        filter = TestRunFilter.objects.get(owner=request.user, name=request.GET['name'])
    except TestRunFilter.DoesNotExist:
        filter = None
    form = TestRunFilterForm(request.user, request.GET, instance=filter)
    if not form.is_valid():
        raise ValidationError(str(form.errors))
    return FilterPreviewTable.json(request, params=(request.user, form))


@BreadCrumb("Filter ~{username}/{name}", parent=filters_list, needs=['username', 'name'])
def filter_detail(request, username, name):
    filter = TestRunFilter.objects.get(owner__username=username, name=name)
    if not filter.public and filter.owner != request.user:
        raise PermissionDenied()
    if not request.user.is_authenticated():
        subscription = None
    else:
        try:
            subscription = TestRunFilterSubscription.objects.get(
                user=request.user, filter=filter)
        except TestRunFilterSubscription.DoesNotExist:
            subscription = None
    return render_to_response(
        'dashboard_app/filter_detail.html', {
            'filter': filter,
            'subscription': subscription,
            'filter_table': FilterTable(
                "filter-table",
                reverse(filter_json, kwargs=dict(username=username, name=name)),
                params=(request.user, filter)),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                filter_detail, name=name, username=username),
        }, RequestContext(request)
    )


@BreadCrumb("Manage Subscription", parent=filter_detail, needs=['name', 'username'])
@login_required
def filter_subscribe(request, username, name):
    filter = TestRunFilter.objects.get(owner__username=username, name=name)
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


def filter_form(request, bread_crumb_trail, instance=None):
    if request.method == 'POST':
        form = TestRunFilterForm(request.user, request.POST, instance=instance)

        if form.is_valid():
            if 'save' in request.POST:
                filter = form.save()
                return HttpResponseRedirect(filter.get_absolute_url())
            else:
                c = request.POST.copy()
                c.pop('csrfmiddlewaretoken', None)
                return render_to_response(
                    'dashboard_app/filter_preview.html', {
                        'bread_crumb_trail': bread_crumb_trail,
                        'form': form,
                        'table': FilterPreviewTable(
                            'filter-preview',
                            reverse(filter_preview_json) + '?' + c.urlencode(),
                            params=(request.user, form)),
                    }, RequestContext(request))
    else:
        form = TestRunFilterForm(request.user, instance=instance)

    return render_to_response(
        'dashboard_app/filter_add.html', {
            'bread_crumb_trail': bread_crumb_trail,
            'form': form,
        }, RequestContext(request))


@BreadCrumb("Add new filter", parent=filters_list)
def filter_add(request):
    return filter_form(
        request,
        BreadCrumbTrail.leading_to(filter_add))


@BreadCrumb("Edit", parent=filter_detail, needs=['name', 'username'])
def filter_edit(request, username, name):
    if request.user.username != username:
        raise PermissionDenied()
    filter = TestRunFilter.objects.get(owner=request.user, name=name)
    return filter_form(
        request,
        BreadCrumbTrail.leading_to(filter_edit, name=name, username=username),
        instance=filter)


@BreadCrumb("Delete", parent=filter_detail, needs=['name', 'username'])
def filter_delete(request, username, name):
    if request.user.username != username:
        raise PermissionDenied()
    filter = TestRunFilter.objects.get(owner=request.user, name=name)
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
    test = Test.objects.get(test_id=request.GET['test'])
    result = TestCase.objects.filter(test=test).order_by('test_case_id').values('test_case_id', 'id')
    return HttpResponse(
        json.dumps(list(result)),
        mimetype='application/json')


def filter_attr_name_completion_json(request):
    term = request.GET['term']
    content_type_id = ContentType.objects.get_for_model(TestRun).id
    result = NamedAttribute.objects.filter(
        name__startswith=term, content_type_id=content_type_id
        ).distinct().order_by('name').values_list('name', flat=True)
    return HttpResponse(
        json.dumps(list(result)),
        mimetype='application/json')


def filter_attr_value_completion_json(request):
    name = request.GET['name']
    term = request.GET['term']
    content_type_id = ContentType.objects.get_for_model(TestRun).id
    result = NamedAttribute.objects.filter(
        name=name, content_type_id=content_type_id, value__startswith=term
        ).distinct().order_by('value').values_list('value', flat=True)
    return HttpResponse(
        json.dumps(list(result)),
        mimetype='application/json')

