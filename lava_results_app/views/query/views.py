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
import os
import shutil
import simplejson
import tempfile

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.core import serializers
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
    FieldError
)
from django.core.urlresolvers import reverse
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect
)
from django.shortcuts import get_object_or_404, render_to_response
from django.template import RequestContext, defaultfilters
from django.utils.safestring import mark_safe

from dashboard_app.models import NamedAttribute
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
    QueryUpdatedError,
    TestCase,
    TestSuite
)

from lava_results_app.views.query.tables import (
    UserQueryTable,
    OtherQueryTable,
    GroupQueryTable,
    QueryTestJobTable,
    QueryTestCaseTable,
    QueryTestSuiteTable,
)

from lava_scheduler_app.models import TestJob

from django.contrib.contenttypes.models import ContentType
from django_tables2 import (
    RequestConfig,
)

from lava.utils.lavatable import LavaView


CONDITIONS_SEPARATOR = ','
CONDITION_DIVIDER = '__'


class InvalidConditionsError(Exception):
    """ Raise when querying by URL has incorrect condition arguments. """


class InvalidContentTypeError(Exception):
    """ Raise when querying by URL content type (table name). """


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
    TestJob: QueryTestJobTable,
    TestCase: QueryTestCaseTable,
    TestSuite: QueryTestSuiteTable,
}


class QueryCustomResultView(LavaView):

    def __init__(self, content_type, conditions,
                 request, **kwargs):
        self.content_type = content_type
        self.conditions = conditions
        self.request = request
        super(QueryCustomResultView, self).__init__(request, **kwargs)

    def get_queryset(self):
        return Query.get_queryset(self.content_type,
                                  self.conditions).visible_by_user(user)


class QueryResultView(LavaView):

    def __init__(self, query, request, **kwargs):
        self.query = query
        self.request = request
        super(QueryResultView, self).__init__(request, **kwargs)

    def get_queryset(self):
        return self.query.get_results(self.request.user)


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
def query_display(request, username, name):

    query = get_object_or_404(Query, owner__username=username, name=name)

    view = QueryResultView(
        query=query,
        request=request,
        model=query.content_type.model_class(),
        table_class=QUERY_CONTENT_TYPE_TABLE[query.content_type.model_class()]
    )

    table = QUERY_CONTENT_TYPE_TABLE[query.content_type.model_class()](
        view.get_table_data()
    )

    config = RequestConfig(request, paginate={"per_page": table.length})
    config.configure(table)

    return render_to_response(
        'lava_results_app/query_display.html', {
            'query': query,
            'entity': query.content_type.model,
            'conditions': _serialize_conditions(query),
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

    content_type = _get_content_type(request.GET.get("entity"))

    if content_type.model_class() not in QueryCondition.RELATION_MAP:
        raise InvalidContentTypeError(
            "Wrong table name in entity param. Please refer to query docs.")

    view = QueryCustomResultView(
        content_type=content_type,
        conditions=_parse_conditions(content_type,
                                     request.GET.get("conditions")),
        request=request,
        model=content_type.model_class(),
        table_class=QUERY_CONTENT_TYPE_TABLE[content_type.model_class()]
    )

    try:
        table = QUERY_CONTENT_TYPE_TABLE[content_type.model_class()](
            view.get_table_data()
        )
    except FieldError:
        raise InvalidConditionsError("Conditions URL incorrect: Field does "
                                     "not exist. Please refer to query docs.")

    config = RequestConfig(request, paginate={"per_page": table.length})
    config.configure(table)

    return render_to_response(
        'lava_results_app/query_custom.html', {
            'query_table': table,

            'terms_data': table.prepare_terms_data(view),
            'search_data': table.prepare_search_data(view),
            'discrete_data': table.prepare_discrete_data(view),

            'bread_crumb_trail': BreadCrumbTrail.leading_to(query_custom),
            'context_help': BreadCrumbTrail.leading_to(query_list),
        }, RequestContext(request)
    )


def _parse_conditions(content_type, conditions):
    # Parse conditions from text representation.

    if not conditions:
        return []

    conditions_objects = []
    for condition_str in conditions.split(CONDITIONS_SEPARATOR):
        condition = QueryCondition()
        condition_fields = condition_str.split(CONDITION_DIVIDER)
        if len(condition_fields) == 3:
            condition.table = content_type
            condition.field = condition_fields[0]
            condition.operator = condition_fields[1]
            condition.value = condition_fields[2]
        elif len(condition_fields) == 4:

            try:
                content_type = _get_content_type(condition_fields[0])
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


def _serialize_conditions(query):
    # Serialize conditions into string.

    conditions_list = []
    for condition in query.querycondition_set.all():
        conditions_list.append("%s%s%s%s%s%s%s" % (
            condition.table.model,
            CONDITION_DIVIDER,
            condition.field,
            CONDITION_DIVIDER,
            condition.operator,
            CONDITION_DIVIDER,
            condition.value
        ))

    return CONDITIONS_SEPARATOR.join(conditions_list)


def _get_content_type(model_name):
    if (model_name == ContentType.objects.get_for_model(TestCase).model):
        return ContentType.objects.get_for_model(TestCase)

    content_types = ContentType.objects.filter(model=model_name)
    if (len(content_types) == 0):
        raise InvalidContentTypeError(
            "Wrong table name in entity param. Please refer to query docs.")
    else:
        return ContentType.objects.filter(model=model_name)[0]


@BreadCrumb("Query ~{username}/{name}", parent=query_list,
            needs=['username', 'name'])
@login_required
@ownership_required
def query_detail(request, username, name):

    query = get_object_or_404(Query, owner__username=username, name=name)
    query_conditions = _serialize_conditions(query)

    return render_to_response(
        'lava_results_app/query_detail.html', {
            'query': query,
            'query_conditions': query_conditions,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                query_detail, username=username, name=name),
            'context_help': BreadCrumbTrail.leading_to(query_list),
            'condition_form': QueryConditionForm(
                instance=None,
                initial={'query': query, 'table': query.content_type}),
        }, RequestContext(request)
    )


@BreadCrumb("Add new", parent=query_list)
@login_required
def query_add(request):

    query = Query()
    query.owner = request.user

    if request.GET.get("entity"):
        query.content_type = _get_content_type(request.GET.get("entity"))

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
def query_export(request, username, name):
    """
    Create and serve the CSV file.
    """
    query = get_object_or_404(Query, owner__username=username, name=name)

    results = query.get_results(request.user)
    filename = "query_%s_%s_export" % (query.owner.username, query.name)
    return _export_query(results, query.content_type, filename)


@login_required
def query_export_custom(request):
    """
    Create and serve the CSV file.
    """

    try:
        content_type = _get_content_type(request.GET.get("entity"))
    except ContentType.DoesNotExist:
        raise InvalidContentTypeError(
            "Wrong table name in entity param. Please refer to query docs.")

    if content_type.model_class() not in QueryCondition.RELATION_MAP:
        raise InvalidContentTypeError(
            "Wrong table name in entity param. Please refer to query docs.")

    conditions = _parse_conditions(content_type, request.GET.get("conditions"))

    filename = "query_%s_export" % (content_type)

    try:
        results = Query.get_queryset(content_type, conditions).visible_by_user(
            user)
    except FieldError:
        raise InvalidConditionsError("Conditions URL incorrect: Field does "
                                     "not exist. Please refer to query docs.")

    return _export_query(results, content_type, filename)


@login_required
@ownership_required
def query_toggle_published(request, username, name):

    query = get_object_or_404(Query, owner__username=username, name=name)

    query.is_published = not query.is_published
    query.save()

    return HttpResponseRedirect(query.get_absolute_url() + "/+detail")


@BreadCrumb("Copy", parent=query_detail, needs=['username', 'name'])
@login_required
@ownership_required
def query_copy(request, username, name):
    query = get_object_or_404(Query, owner__username=username, name=name)

    if not request.user.is_superuser:
        if query.owner != request.user:
            if not query.group or not request.user.groups.filter(
                    name=query.group.name).exists():
                raise PermissionDenied()

    return query_form(
        request,
        BreadCrumbTrail.leading_to(query_copy, name=name, username=username),
        instance=query,
        is_copy=True)


@login_required
def query_refresh(request, name, username):

    query = get_object_or_404(Query, owner__username=username, name=name)

    success = True
    error_msg = None
    try:
        query.refresh_view()
    except QueryUpdatedError as e:
        error_msg = str(e)
        success = False
    except Exception as e:
        raise

    last_updated = defaultfilters.date(query.last_updated, "DATETIME_FORMAT")
    return HttpResponse(simplejson.dumps([success, str(last_updated),
                                          error_msg]),
                        content_type='application/json')


@login_required
def query_group_list(request):

    term = request.GET['term']
    groups = [str(group.name) for group in QueryGroup.objects.filter(
        name__istartswith=term)]
    return HttpResponse(simplejson.dumps(groups),
                        content_type='application/json')


@login_required
def query_add_group(request, username, name):

    if request.method != 'POST':
        raise PermissionDenied

    group_name = request.POST.get("value")
    query = get_object_or_404(Query, owner__username=username, name=name)
    old_group = query.query_group

    if not group_name:
        query.query_group = None
    else:
        new_group = QueryGroup.objects.get_or_create(name=group_name)[0]
        query.query_group = new_group

    query.save()

    if old_group:
        if not old_group.query_set.count():
            old_group.delete()

    return HttpResponse(group_name, content_type='application/json')


@login_required
@ownership_required
def query_select_group(request, username, name):

    if request.method != 'POST':
        raise PermissionDenied

    group_name = request.POST.get("value")
    query = get_object_or_404(Query, owner__username=username, name=name)

    if not group_name:
        query.group = None
    else:
        group = Group.objects.get(name=group_name)
        query.group = group

    query.save()

    return HttpResponse(group_name, content_type='application/json')


@login_required
def get_group_names(request):

    term = request.GET['term']
    groups = []
    for group in Group.objects.filter(user=request.user,
                                      name__istartswith=term):
        groups.append(
            {"id": group.id,
             "name": group.name,
             "label": group.name})
    return HttpResponse(simplejson.dumps(groups),
                        content_type='application/json')


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


def query_form(request, bread_crumb_trail, instance=None, is_copy=False):

    if request.method == 'POST':

        form = QueryForm(request.user, request.POST,
                         instance=instance, is_copy=is_copy)
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
        form = QueryForm(request.user, instance=instance, is_copy=is_copy)
        form.fields['owner'].initial = request.user

    query_name = None
    if is_copy:
        query_name = instance.name
        instance.name = None

    return render_to_response(
        'lava_results_app/query_form.html', {
            'bread_crumb_trail': bread_crumb_trail,
            'is_copy': is_copy,
            'query_name': query_name,
            'form': form,
        }, RequestContext(request))


def query_condition_form(request, query,
                         bread_crumb_trail, instance=None):

    form = QueryConditionForm(request.POST, instance=instance)

    if form.is_valid():
        query_condition = form.save()

        return HttpResponse(
            serializers.serialize(
                "json", [query_condition, query_condition.table]),
            content_type='application/json')
    else:
        return HttpResponse(simplejson.dumps(["fail", form.errors]),
                            content_type='application/json')


def _remove_dir(path):
    """ Removes directory @path. Doesn't raise exceptions. """
    try:
        # Delete directory.
        shutil.rmtree(path)
    except OSError as exception:
        # Silent exception whatever happens. If it's unexisting dir, we don't
        # care.
        pass


def _export_query(query_results, content_type, filename):

    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, "%s.csv" % filename)

    query_keys = content_type.model_class()._meta.get_all_field_names()

    query_keys.sort()
    # Remove non-relevant columns for CSV file.
    removed_fields = [
        # TestJob fields:
        "_results_bundle", "_results_bundle_id", "_results_link", "user_id",
        "actual_device_id", "definition", "group_id", "id",
        "original_definition", "requested_device_id", "sub_id", "submit_token",
        "submit_token_id", "submitter_id", "testdata", "testsuite",
        # TestSuite fields:
        "job_id",
        # TestCase fields:
        "actionlevels", "suite_id", "test_set_id"
    ]
    for field in removed_fields:
        if field in query_keys:
            query_keys.remove(field)

    with open(file_path, 'wb+') as csv_file:
        out = csv.DictWriter(csv_file, quoting=csv.QUOTE_ALL,
                             extrasaction='ignore',
                             fieldnames=query_keys)
        out.writeheader()

        for result in query_results:

            result_dict = result.__dict__.copy()
            out.writerow(result_dict)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = "attachment; filename=%s.csv" % filename
    with open(file_path, 'r') as csv_file:
        response.write(csv_file.read())

    _remove_dir(tmp_dir)
    return response
