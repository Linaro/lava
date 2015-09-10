# Copyright (C) 2015 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
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

import csv
import simplejson
import os
import tempfile

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.core import serializers
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.urlresolvers import reverse
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect
)
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext
from django.utils.safestring import mark_safe

from lava_server.bread_crumbs import (
    BreadCrumb,
    BreadCrumbTrail,
)

from lava_results_app.views import index
from lava_results_app.views.query.decorators import ownership_required
from lava_results_app.views.query.forms import (
    QueryForm,
    QueryConditionForm,
)

from lava_results_app.models import (
    Query,
    QueryGroup,
    QueryCondition,
)

from lava_results_app.views.query.tables import (
    UserQueryTable,
    OtherQueryTable,
    GroupQueryTable,
    QueryTestJobTable,
    QueryTestCaseTable,
    QueryTestSuiteTable,
    QueryTestSetTable,
)

from lava_scheduler_app.models import TestJob

from django.contrib.contenttypes.models import ContentType
from django_tables2 import (
    RequestConfig,
)

from lava.utils.lavatable import LavaView


class InvalidConditionsError(Exception):
    ''' Raise when querying by URL has incorrect condition arguments. '''
    pass


class UserQueryView(LavaView):

    def get_queryset(self):
        return Query.objects.filter(owner=self.request.user).order_by('name')


class OtherQueryView(LavaView):

    def get_queryset(self):
        # All published queries which are not part
        # of any group.
        other_queries = Query.objects.filter(is_published=True,
                                             query_group=None).order_by('name')

        return other_queries


class GroupQueryView(LavaView):

    def __init__(self, request, group, **kwargs):
        super(GroupQueryView, self).__init__(request, **kwargs)
        self.query_group = group

    def get_queryset(self):
        # Specific group queries.
        group_queries = Query.objects.filter(
            is_published=True,
            query_group=self.query_group).order_by('name')

        return group_queries


QUERY_CONTENT_TYPE_TABLE = {
    "testjob": QueryTestJobTable,
    "testcase": QueryTestCaseTable,
    "testsuite": QueryTestSuiteTable,
    "testset": QueryTestSetTable
}


class QueryResultView(LavaView):

    def __init__(self, content_type, conditions,
                 request, **kwargs):
        self.content_type = content_type
        self.conditions = conditions
        self.request = request
        super(QueryResultView, self).__init__(request, **kwargs)

    def get_queryset(self):
        return Query.get_results(self.content_type, self.conditions)


@BreadCrumb("Queries", parent=index)
def query_list(request):

    group_tables = {}
    terms_data = search_data = discrete_data = {}
    for group in QueryGroup.objects.all():
        if group.query_set.count():
            prefix = "group_%s_" % group.id
            group_view = GroupQueryView(request, group, model=Query,
                                        table_class=GroupQueryTable)
            table = GroupQueryTable(group_view.get_table_data(prefix),
                                    prefix=prefix)
            search_data.update(table.prepare_search_data(group_view))
            discrete_data.update(table.prepare_discrete_data(group_view))
            terms_data.update(table.prepare_terms_data(group_view))
            group_tables[group.name] = table
            config = RequestConfig(request,
                                   paginate={"per_page": table.length})
            config.configure(table)

    prefix = "other_"
    other_view = OtherQueryView(request, model=Query,
                                table_class=OtherQueryTable)
    other_query_table = OtherQueryTable(other_view.get_table_data(prefix),
                                        prefix=prefix)
    config = RequestConfig(request,
                           paginate={"per_page": other_query_table.length})
    config.configure(other_query_table)
    search_data.update(other_query_table.prepare_search_data(other_view))
    discrete_data.update(other_query_table.prepare_discrete_data(other_view))
    terms_data.update(other_query_table.prepare_terms_data(other_view))

    if request.user.is_authenticated():
        prefix = "user_"
        view = UserQueryView(request, model=Query, table_class=UserQueryTable)
        user_query_table = UserQueryTable(view.get_table_data(prefix),
                                          prefix=prefix)
        config = RequestConfig(request,
                               paginate={"per_page": user_query_table.length})
        config.configure(user_query_table)
        search_data.update(user_query_table.prepare_search_data(view))
        discrete_data.update(user_query_table.prepare_discrete_data(view))
        terms_data.update(user_query_table.prepare_terms_data(view))
    else:
        user_query_table = None

    return render_to_response(
        'lava_results_app/query_list.html', {
            'user_query_table': user_query_table,
            'other_query_table': other_query_table,
            'search_data': search_data,
            "discrete_data": discrete_data,
            'terms_data': terms_data,
            'group_tables': group_tables,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(query_list),
            'context_help': BreadCrumbTrail.leading_to(query_list),
        }, RequestContext(request)
    )


@BreadCrumb("Query ~{username}/{name}", parent=query_list,
            needs=['username', 'name'])
@login_required
@ownership_required
def query_display(request, username, name):

    query = get_object_or_404(Query, owner__username=username, name=name)

    view = QueryResultView(
        content_type=query.content_type,
        conditions=query.querycondition_set.all(),
        request=request,
        model=query.content_type.model_class(),
        table_class=QUERY_CONTENT_TYPE_TABLE[query.content_type.model]
    )

    table = QUERY_CONTENT_TYPE_TABLE[query.content_type.model](
        view.get_table_data()
    )

    config = RequestConfig(request, paginate={"per_page": table.length})
    config.configure(table)

    return render_to_response(
        'lava_results_app/query_display.html', {
            'query': query,
            'entity': query.content_type.model,
            'conditions': _join_conditions(query),
            'query_table': table,
            'terms_data': table.prepare_terms_data(view),
            'search_data': table.prepare_search_data(view),
            'discrete_data': table.prepare_discrete_data(view),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                query_display, username=username, name=name),
            'context_help': BreadCrumbTrail.leading_to(query_list),
        }, RequestContext(request)
    )


@BreadCrumb("Custom Query", parent=query_list)
@login_required
def query_custom(request):

    # TODO: validate entity as content_type
    # TODO: validate conditions

    content_type = ContentType.objects.get(
        model=request.GET.get("entity"),
        app_label=_get_app_label_for_model(request.GET.get("entity"))
    )

    view = QueryResultView(
        content_type=content_type,
        conditions=_parse_conditions(content_type,
                                     request.GET.get("conditions")),
        request=request,
        model=content_type.model_class(),
        table_class=QUERY_CONTENT_TYPE_TABLE[content_type.model]
    )

    table = QUERY_CONTENT_TYPE_TABLE[content_type.model](
        view.get_table_data()
    )

    return render_to_response(
        'lava_results_app/query_custom.html', {
            'query_table': table,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(query_custom),
            'context_help': BreadCrumbTrail.leading_to(query_list),
        }, RequestContext(request)
    )


def _parse_conditions(content_type, conditions):
    # Parse conditions from request.

    conditions_objects = []
    for condition_str in conditions.split(","):
        condition = QueryCondition()
        condition_fields = condition_str.split("__")
        if len(condition_fields) == 3:
            condition.table = content_type
            condition.field = condition_fields[0]
            condition.operator = condition_fields[1]
            condition.value = condition_fields[2]
        elif len(condition_fields) == 4:
            content_type = ContentType.objects.get(
                model=condition_fields[0],
                app_label=_get_app_label_for_model(condition_fields[0])
            )
            condition.table = content_type
            condition.field = condition_fields[1]
            condition.operator = condition_fields[2]
            condition.value = condition_fields[3]

        else:
            # TODO: more validation for conditions?.
            raise InvalidConditionsError("Conditions URL incorrect.")

        conditions_objects.append(condition)

    return conditions_objects


def _join_conditions(query):
    # Join conditions for query by URL.
    conditions = None
    for condition in query.querycondition_set.all():
        if conditions:
            conditions += ','
        else:
            conditions = ''
        conditions += '{0}__{1}__{2}__{3}'.format(
            condition.table.model,
            condition.field,
            condition.operator,
            condition.value
        )

    return conditions


def _get_app_label_for_model(model_name):
    # Every model currently used is in 'lava_results_app', except the
    # TestJob, hence the hack.

    app_label = Query._meta.app_label
    if model_name == "testjob":
        app_label = TestJob._meta.app_label

    return app_label


@BreadCrumb("Query ~{username}/{name}", parent=query_list,
            needs=['username', 'name'])
@login_required
@ownership_required
def query_detail(request, username, name):

    query = get_object_or_404(Query, owner__username=username, name=name)

    return render_to_response(
        'lava_results_app/query_detail.html', {
            'query': query,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                query_detail, username=username, name=name),
            'context_help': BreadCrumbTrail.leading_to(query_list),
            'condition_form': QueryConditionForm(
                request.user, instance=None,
                initial={'query': query, 'table': query.content_type}),
        }, RequestContext(request)
    )


@BreadCrumb("Add new", parent=query_list)
@login_required
def query_add(request):

    query = Query()
    query.owner = request.user

    if request.GET.get("entity"):
        query.content_type = ContentType.objects.get(
            model=request.GET.get("entity"),
            app_label=_get_app_label_for_model(request.GET.get("entity"))
        )

    return query_form(
        request,
        BreadCrumbTrail.leading_to(query_add),
        instance=query)


@BreadCrumb("Edit ~{username}/{name}", parent=query_detail,
            needs=['username', 'name'])
@login_required
@ownership_required
def query_edit(request, username, name):

    query = get_object_or_404(Query, owner__username=username, name=name)

    return query_form(
        request,
        BreadCrumbTrail.leading_to(query_edit, username=username, name=name),
        instance=query)


@login_required
@ownership_required
def query_delete(request, username, name):

    query = get_object_or_404(Query, owner__username=username, name=name)

    query.delete()
    return HttpResponseRedirect(reverse(
        'lava.results.query_list'))


@login_required
@ownership_required
def query_toggle_published(request, username, name):

    query = get_object_or_404(Query, owner__username=username, name=name)

    query.is_published = not query.is_published
    query.save()

    return HttpResponseRedirect(query.get_absolute_url() + "/+detail")


@login_required
@ownership_required
def query_add_condition(request, username, name):

    query = get_object_or_404(Query, owner__username=username, name=name)

    return query_condition_form(
        request, query,
        BreadCrumbTrail.leading_to(query_add))


@login_required
@ownership_required
def query_edit_condition(request, username, name, id):

    query = get_object_or_404(Query, owner__username=username, name=name)
    query_condition = get_object_or_404(QueryCondition, id=id)

    return query_condition_form(
        request, query,
        BreadCrumbTrail.leading_to(query_add),
        instance=query_condition)


@login_required
@ownership_required
def query_remove_condition(request, username, name, id):

    query = get_object_or_404(Query, owner__username=username, name=name)
    query_condition = get_object_or_404(QueryCondition, id=id)
    query_condition.delete()

    return HttpResponseRedirect(query.get_absolute_url() + "/+detail")


def query_form(request, bread_crumb_trail, instance=None):

    if request.method == 'POST':

        form = QueryForm(request.user, request.POST,
                         instance=instance)
        if form.is_valid():
            query = form.save()
            if request.GET.get("conditions"):
                conditions = _parse_conditions(query.content_type,
                                               request.GET.get("conditions"))
                for condition in conditions:
                    condition.query = query
                    condition.save()

            return HttpResponseRedirect(query.get_absolute_url() + "/+detail")

    else:
        form = QueryForm(request.user, instance=instance)
        form.fields['owner'].initial = request.user

    return render_to_response(
        'lava_results_app/query_form.html', {
            'bread_crumb_trail': bread_crumb_trail,
            'form': form,
        }, RequestContext(request))


def query_condition_form(request, query,
                         bread_crumb_trail, instance=None):

    form = QueryConditionForm(request.user, request.POST, instance=instance)

    if form.is_valid():
        query_condition = form.save()

        return HttpResponse(
            serializers.serialize(
                "json", [query_condition, query_condition.table]),
            content_type='application/json')
    else:
        return HttpResponse(simplejson.dumps(["fail", form.errors]),
                            content_type='application/json')
