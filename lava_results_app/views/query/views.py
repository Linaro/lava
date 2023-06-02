# Copyright (C) 2015-2018 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import csv
import os
import shutil
import tempfile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core import serializers
from django.core.exceptions import FieldDoesNotExist, FieldError, PermissionDenied
from django.db import IntegrityError
from django.db.models import Q
from django.db.utils import ProgrammingError
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, loader
from django.template import defaultfilters
from django.urls import reverse
from django_tables2 import RequestConfig

from lava_results_app.models import (
    InvalidConditionsError,
    InvalidContentTypeError,
    Query,
    QueryCondition,
    QueryGroup,
    QueryOmitResult,
    QueryUpdatedError,
    TestCase,
    TestSuite,
)
from lava_results_app.views import index
from lava_results_app.views.query.decorators import ownership_required
from lava_results_app.views.query.forms import QueryConditionForm, QueryForm
from lava_results_app.views.query.tables import (
    GroupQueryTable,
    OtherQueryTable,
    QueryTestCaseTable,
    QueryTestJobTable,
    QueryTestSuiteTable,
    UserQueryTable,
)
from lava_scheduler_app.models import TestJob
from lava_server.bread_crumbs import BreadCrumb, BreadCrumbTrail
from lava_server.lavatable import LavaView


class QueryViewDoesNotExistError(Exception):
    """Raise when corresponding query materialized view does not exist."""


class UserQueryView(LavaView):
    def get_queryset(self):
        return Query.objects.filter(
            is_archived=False, owner__id=self.request.user.id
        ).order_by("name")


class OtherQueryView(LavaView):
    def get_queryset(self):
        # All published queries which are not part
        # of any group.
        other_queries = (
            Query.objects.filter(is_archived=False, is_published=True, query_group=None)
            .exclude(owner__id=self.request.user.id)
            .order_by("name")
        )

        return other_queries


class GroupQueryView(LavaView):
    def __init__(self, request, group, **kwargs):
        super().__init__(request, **kwargs)
        self.query_group = group

    def get_queryset(self):
        # Specific group queries.
        group_queries = (
            Query.objects.filter(
                is_archived=False, is_published=True, query_group=self.query_group
            )
            .exclude(owner__id=self.request.user.id)
            .order_by("name")
        )

        return group_queries


QUERY_CONTENT_TYPE_TABLE = {
    TestJob: QueryTestJobTable,
    TestCase: QueryTestCaseTable,
    TestSuite: QueryTestSuiteTable,
}


class QueryCustomResultView(LavaView):
    def __init__(self, content_type, conditions, request, **kwargs):
        self.content_type = content_type
        self.conditions = conditions
        self.request = request
        super().__init__(request, **kwargs)

    def get_queryset(self):
        return Query.get_queryset(self.content_type, self.conditions).visible_by_user(
            self.request.user
        )


class QueryResultView(LavaView):
    def __init__(self, query, request, **kwargs):
        self.query = query
        self.request = request
        super().__init__(request, **kwargs)

    def get_queryset(self):
        return self.query.get_results(self.request.user)


@BreadCrumb("Queries", parent=index)
def query_list(request):
    group_tables = {}
    terms_data = search_data = discrete_data = {}
    for group in QueryGroup.objects.all():
        if group.query_set.count():
            prefix = "group_%s_" % group.id
            group_view = GroupQueryView(
                request, group, model=Query, table_class=GroupQueryTable
            )
            table = GroupQueryTable(
                group_view.get_table_data(prefix), request=request, prefix=prefix
            )
            search_data.update(table.prepare_search_data(group_view))
            discrete_data.update(table.prepare_discrete_data(group_view))
            terms_data.update(table.prepare_terms_data(group_view))
            group_tables[group.name] = table
            config = RequestConfig(request, paginate={"per_page": table.length})
            config.configure(table)

    prefix = "other_"
    other_view = OtherQueryView(request, model=Query, table_class=OtherQueryTable)
    other_query_table = OtherQueryTable(
        other_view.get_table_data(prefix), request=request, prefix=prefix
    )
    config = RequestConfig(request, paginate={"per_page": other_query_table.length})
    config.configure(other_query_table)
    search_data.update(other_query_table.prepare_search_data(other_view))
    discrete_data.update(other_query_table.prepare_discrete_data(other_view))
    terms_data.update(other_query_table.prepare_terms_data(other_view))

    prefix = "user_"
    view = UserQueryView(request, model=Query, table_class=UserQueryTable)
    user_query_table = UserQueryTable(
        view.get_table_data(prefix), request=request, prefix=prefix
    )
    config = RequestConfig(request, paginate={"per_page": user_query_table.length})
    config.configure(user_query_table)
    search_data.update(user_query_table.prepare_search_data(view))
    discrete_data.update(user_query_table.prepare_discrete_data(view))
    terms_data.update(user_query_table.prepare_terms_data(view))

    template = loader.get_template("lava_results_app/query_list.html")
    return HttpResponse(
        template.render(
            {
                "user_query_table": user_query_table,
                "other_query_table": other_query_table,
                "search_data": search_data,
                "discrete_data": discrete_data,
                "terms_data": terms_data,
                "group_tables": group_tables,
                "bread_crumb_trail": BreadCrumbTrail.leading_to(query_list),
                "context_help": ["lava-queries-charts"],
            },
            request=request,
        )
    )


@BreadCrumb("Query ~{username}/{name}", parent=query_list, needs=["username", "name"])
def query_display(request, username, name):
    query = get_object_or_404(Query, owner__username=username, name=name)

    if not request.user.is_superuser:
        if not query.is_published and query.owner != request.user:
            raise PermissionDenied

    view = QueryResultView(
        query=query,
        request=request,
        model=query.content_type.model_class(),
        table_class=QUERY_CONTENT_TYPE_TABLE[query.content_type.model_class()],
    )

    table = QUERY_CONTENT_TYPE_TABLE[query.content_type.model_class()](
        query, request.user, view.get_table_data()
    )

    try:
        config = RequestConfig(request, paginate={"per_page": table.length})
        config.configure(table)
    except ProgrammingError:
        raise QueryViewDoesNotExistError(
            "Query view does not exist. Please contact query owner or system "
            "administrator."
        )

    omitted = [
        result.content_object for result in QueryOmitResult.objects.filter(query=query)
    ]
    template = loader.get_template("lava_results_app/query_display.html")
    return HttpResponse(
        template.render(
            {
                "query": query,
                "entity": query.content_type.model,
                "conditions": Query.serialize_conditions(
                    query.querycondition_set.all()
                ),
                "omitted": omitted,
                "query_table": table,
                "terms_data": table.prepare_terms_data(view),
                "search_data": table.prepare_search_data(view),
                "discrete_data": table.prepare_discrete_data(view),
                "bread_crumb_trail": BreadCrumbTrail.leading_to(
                    query_display, username=username, name=name
                ),
                "context_help": ["lava-queries-charts"],
            },
            request=request,
        )
    )


@BreadCrumb("Custom Query", parent=query_list)
@login_required
def query_custom(request):
    try:
        content_type = Query.get_content_type(request.GET.get("entity"))
    except InvalidContentTypeError as e:
        messages.error(request, e)
        raise Http404()

    if content_type.model_class() not in QueryCondition.RELATION_MAP:
        messages.error(
            request, "Wrong table name in entity param. Please refer to query docs."
        )
        raise Http404()

    try:
        conditions = Query.parse_conditions(content_type, request.GET.get("conditions"))
    except InvalidConditionsError as e:
        messages.error(request, e)
        raise Http404()

    view = QueryCustomResultView(
        content_type=content_type,
        conditions=conditions,
        request=request,
        model=content_type.model_class(),
        table_class=QUERY_CONTENT_TYPE_TABLE[content_type.model_class()],
    )

    try:
        table = QUERY_CONTENT_TYPE_TABLE[content_type.model_class()](
            None, request.user, view.get_table_data()
        )
    except (FieldDoesNotExist, FieldError) as e:
        messages.error(request, e)
        raise Http404()

    config = RequestConfig(request, paginate={"per_page": table.length})
    config.configure(table)
    template = loader.get_template("lava_results_app/query_custom.html")
    return HttpResponse(
        template.render(
            {
                "query_table": table,
                "conditions": conditions,
                "terms_data": table.prepare_terms_data(view),
                "search_data": table.prepare_search_data(view),
                "discrete_data": table.prepare_discrete_data(view),
                "bread_crumb_trail": BreadCrumbTrail.leading_to(query_custom),
                "context_help": ["lava-queries-charts"],
            },
            request=request,
        )
    )


@BreadCrumb("Query ~{username}/{name}", parent=query_list, needs=["username", "name"])
@login_required
def query_detail(request, username, name):
    query = get_object_or_404(Query, owner__username=username, name=name)
    query_conditions = Query.serialize_conditions(query.querycondition_set.all())
    template = loader.get_template("lava_results_app/query_detail.html")
    return HttpResponse(
        template.render(
            {
                "query": query,
                "query_conditions": query_conditions,
                "bread_crumb_trail": BreadCrumbTrail.leading_to(
                    query_detail, username=username, name=name
                ),
                "context_help": ["lava-queries-charts"],
                "condition_form": QueryConditionForm(
                    instance=None, initial={"query": query, "table": query.content_type}
                ),
            },
            request=request,
        )
    )


@BreadCrumb("Add new", parent=query_list)
@login_required
def query_add(request):
    query = Query()
    query.owner = request.user

    if request.GET.get("entity"):
        query.content_type = Query.get_content_type(request.GET.get("entity"))

    return query_form(request, BreadCrumbTrail.leading_to(query_add), instance=query)


@BreadCrumb("Edit ~{username}/{name}", parent=query_detail, needs=["username", "name"])
@login_required
@ownership_required
def query_edit(request, username, name):
    query = get_object_or_404(Query, owner__username=username, name=name)

    return query_form(
        request,
        BreadCrumbTrail.leading_to(query_edit, username=username, name=name),
        instance=query,
    )


@login_required
@ownership_required
def query_delete(request, username, name):
    query = get_object_or_404(Query, owner__username=username, name=name)
    query.is_archived = True
    query.save()
    return HttpResponseRedirect(reverse("lava.results.query_list"))


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
        content_type = Query.get_content_type(request.GET.get("entity"))
    except InvalidContentTypeError as e:
        messages.error(request, e)
        raise Http404()

    if content_type.model_class() not in QueryCondition.RELATION_MAP:
        messages.error(
            request, "Wrong table name in entity param. Please refer to query docs."
        )
        raise Http404()

    try:
        conditions = Query.parse_conditions(content_type, request.GET.get("conditions"))
    except InvalidConditionsError as e:
        messages.error(request, e)
        raise Http404()

    filename = "query_%s_export" % (content_type)

    try:
        results = Query.get_queryset(content_type, conditions).visible_by_user(
            request.user
        )
    except (FieldDoesNotExist, FieldError) as e:
        messages.error(request, e)
        raise Http404()

    return _export_query(results, content_type, filename)


@login_required
@ownership_required
def query_toggle_published(request, username, name):
    query = get_object_or_404(Query, owner__username=username, name=name)

    query.is_published = not query.is_published
    query.save()

    return HttpResponseRedirect(query.get_absolute_url() + "/+detail")


@BreadCrumb("Copy", parent=query_detail, needs=["username", "name"])
@login_required
def query_copy(request, username, name):
    query = get_object_or_404(Query, owner__username=username, name=name)
    query.owner = request.user
    query.is_published = False

    return query_form(
        request,
        BreadCrumbTrail.leading_to(query_copy, name=name, username=username),
        instance=query,
        is_copy=True,
    )


@login_required
@ownership_required
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
        success = False
        error_msg = "%s<br>Please contact system administrator." % str(e)

    last_updated = defaultfilters.date(query.last_updated, "DATETIME_FORMAT")
    return JsonResponse(
        [success, str(last_updated), error_msg],
        safe=False,
    )


@login_required
def query_group_list(request):
    term = request.GET["term"]
    groups = [
        str(group.name) for group in QueryGroup.objects.filter(name__istartswith=term)
    ]
    return JsonResponse(groups, safe=False)


@login_required
def query_add_group(request, username, name):
    if request.method != "POST":
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

    return HttpResponseRedirect(query.get_absolute_url() + "/+detail")


@login_required
@ownership_required
def query_select_group(request, username, name):
    if request.method != "POST":
        raise PermissionDenied

    group_name = request.POST.get("value")
    query = get_object_or_404(Query, owner__username=username, name=name)

    if not group_name:
        query.group = None
    else:
        try:
            group = Group.objects.get(name=group_name)
        except Group.DoesNotExist:
            group = None
        query.group = group

    query.save()

    return HttpResponseRedirect(query.get_absolute_url() + "/+detail")


@login_required
def get_query_group_names(request):
    term = request.GET["term"]
    groups = []
    for group in Group.objects.filter(user=request.user, name__istartswith=term):
        groups.append({"id": group.id, "name": group.name, "label": group.name})
    return JsonResponse(groups, safe=False)


@login_required
@ownership_required
def query_add_condition(request, username, name):
    query = get_object_or_404(Query, owner__username=username, name=name)

    return query_condition_form(request, query, BreadCrumbTrail.leading_to(query_add))


@login_required
@ownership_required
def query_edit_condition(request, username, name, id):
    query = get_object_or_404(Query, owner__username=username, name=name)
    query_condition = get_object_or_404(QueryCondition, id=id)

    return query_condition_form(
        request, query, BreadCrumbTrail.leading_to(query_add), instance=query_condition
    )


@login_required
@ownership_required
def query_remove_condition(request, username, name, id):
    query = get_object_or_404(Query, owner__username=username, name=name)
    query_condition = get_object_or_404(QueryCondition, id=id)
    query_condition.delete()

    return HttpResponseRedirect(query.get_absolute_url() + "/+detail")


@login_required
@ownership_required
def query_omit_result(request, username, name, id):
    query = get_object_or_404(Query, owner__username=username, name=name)
    result_object = get_object_or_404(query.content_type.model_class(), id=id)

    try:
        QueryOmitResult.objects.create(query=query, content_object=result_object)
    except IntegrityError:
        # Ignore unique constraint violation.
        pass

    return HttpResponseRedirect(query.get_absolute_url())


@login_required
@ownership_required
def query_include_result(request, username, name, id):
    query = get_object_or_404(Query, owner__username=username, name=name)
    result_object = get_object_or_404(query.content_type.model_class(), id=id)

    try:
        QueryOmitResult.objects.get(
            query=query, object_id=result_object.id, content_type=query.content_type
        ).delete()
    except QueryOmitResult.DoesNotExist:
        # Ignore does not exist violation.
        raise

    return HttpResponseRedirect(query.get_absolute_url())


def get_query_names(request):
    term = request.GET["term"]
    result = []

    query_list = (
        Query.objects.filter(
            Q(is_archived=False),
            Q(name__istartswith=term) | Q(owner__username__istartswith=term),
        )
        .distinct()
        .order_by("name")
    )
    for query in query_list:
        result.append(
            {
                "value": query.owner_name,
                "label": query.owner_name,
                "id": query.id,
                "content_type": query.content_type.model_class().__name__,
            }
        )
    return JsonResponse(result, safe=False)


def query_form(request, bread_crumb_trail, instance=None, is_copy=False):
    if request.method == "POST":
        form = QueryForm(request.user, request.POST, instance=instance, is_copy=is_copy)
        if form.is_valid():
            query = form.save()
            if request.GET.get("conditions"):
                conditions = Query.parse_conditions(
                    query.content_type, request.GET.get("conditions")
                )
                for condition in conditions:
                    condition.query = query
                    condition.save()

            return HttpResponseRedirect(query.get_absolute_url() + "/+detail")

    else:
        form = QueryForm(request.user, instance=instance, is_copy=is_copy)
        form.fields["owner"].initial = request.user

    query_name = None
    if is_copy:
        query_name = instance.name
        instance.name = None
    template = loader.get_template("lava_results_app/query_form.html")
    return HttpResponse(
        template.render(
            {
                "bread_crumb_trail": bread_crumb_trail,
                "is_copy": is_copy,
                "query_name": query_name,
                "form": form,
                "context_help": ["lava-queries-charts"],
            },
            request=request,
        )
    )


def query_condition_form(request, query, bread_crumb_trail, instance=None):
    form = QueryConditionForm(request.POST, instance=instance)

    if form.is_valid():
        query_condition = form.save()

        return HttpResponse(
            serializers.serialize("json", [query_condition, query_condition.table]),
            content_type="application/json",
        )
    else:
        return JsonResponse(["fail", form.errors], safe=False)


def _remove_dir(path):
    """Removes directory @path. Doesn't raise exceptions."""
    try:
        # Delete directory.
        shutil.rmtree(path)
    except OSError:
        # Silent exception whatever happens. If it's unexisting dir, we don't
        # care.
        pass


def _export_query(query_results, content_type, filename):
    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, "%s.csv" % filename)

    query_keys = [field.name for field in content_type.model_class()._meta.get_fields()]

    query_keys.sort()
    # Remove non-relevant columns for CSV file.
    removed_fields = [
        # TestJob fields:
        "user_id",
        "actual_device_id",
        "definition",
        "group_id",
        "multinode_definition",
        "original_definition",
        "health_check",
        "sub_id",
        "submitter_id",
        "testdata",
        "testsuite",
        "target_group",
        "notification",
        "testjobmaterializedview",
        "testjobuser",
        "pipeline_compatibility",
        # TestSuite fields:
        "job_id",
        # TestCase fields:
        "suite_id",
        "test_set_id",
    ]
    for field in removed_fields:
        if field in query_keys:
            query_keys.remove(field)

    with open(file_path, "w+") as csv_file:
        out = csv.DictWriter(
            csv_file,
            quoting=csv.QUOTE_ALL,
            extrasaction="ignore",
            fieldnames=query_keys,
        )
        out.writeheader()

        for result in query_results:
            result_dict = result.__dict__.copy()
            # Encode the strings if necessary.
            out.writerow(
                {
                    k: (v.encode("utf8") if isinstance(v, str) else v)
                    for k, v in result_dict.items()
                }
            )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=%s.csv" % filename
    with open(file_path) as csv_file:
        response.write(csv_file.read())

    _remove_dir(tmp_dir)
    return response
