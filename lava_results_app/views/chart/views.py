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

import simplejson

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core import serializers
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.db import IntegrityError
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect
)
from django.shortcuts import get_object_or_404, render, loader

from lava_server.bread_crumbs import (
    BreadCrumb,
    BreadCrumbTrail,
)

from lava_results_app.views import index
from lava_results_app.views.chart.decorators import ownership_required
from lava_results_app.views.chart.forms import (
    ChartForm,
    ChartQueryForm,
    ChartQueryUserForm
)

from lava_results_app.models import (
    Query,
    QueryCondition,
    QueryOmitResult,
    Chart,
    ChartGroup,
    ChartQuery,
    ChartQueryUser,
    TestCase,
    InvalidContentTypeError
)

from lava_results_app.views.chart.tables import (
    UserChartTable,
    OtherChartTable,
    GroupChartTable,
)

from django_tables2 import (
    RequestConfig,
)

from lava.utils.lavatable import LavaView


CONDITIONS_SEPARATOR = ','
CONDITION_DIVIDER = '__'


class InvalidChartTypeError(Exception):
    """ Raise when charting by URL has incorrect type argument. """


class TestCasePassFailChartError(Exception):
    """ Raise when test case charts are of pass/fail type. """


class UserChartView(LavaView):

    def get_queryset(self):
        return Chart.objects.filter(owner=self.request.user).order_by('name')


class OtherChartView(LavaView):

    def get_queryset(self):
        # All published charts which are not part
        # of any group.
        other_charts = Chart.objects.filter(is_published=True,
                                            chart_group=None).order_by('name')

        return other_charts


class GroupChartView(LavaView):

    def __init__(self, request, group, **kwargs):
        super(GroupChartView, self).__init__(request, **kwargs)
        self.chart_group = group

    def get_queryset(self):
        # Specific group charts.
        group_charts = Chart.objects.filter(
            is_published=True,
            chart_group=self.chart_group).order_by('name')

        return group_charts


@BreadCrumb("Charts", parent=index)
def chart_list(request):

    group_tables = {}
    terms_data = search_data = discrete_data = {}
    for group in ChartGroup.objects.all():
        if group.chart_set.count():
            prefix = "group_%s_" % group.id
            group_view = GroupChartView(request, group, model=Chart,
                                        table_class=GroupChartTable)
            table = GroupChartTable(group_view.get_table_data(prefix),
                                    prefix=prefix)
            search_data.update(table.prepare_search_data(group_view))
            discrete_data.update(table.prepare_discrete_data(group_view))
            terms_data.update(table.prepare_terms_data(group_view))
            group_tables[group.name] = table
            config = RequestConfig(request,
                                   paginate={"per_page": table.length})
            config.configure(table)

    prefix = "other_"
    other_view = OtherChartView(request, model=Chart,
                                table_class=OtherChartTable)
    other_chart_table = OtherChartTable(other_view.get_table_data(prefix),
                                        prefix=prefix)
    config = RequestConfig(request,
                           paginate={"per_page": other_chart_table.length})
    config.configure(other_chart_table)
    search_data.update(other_chart_table.prepare_search_data(other_view))
    discrete_data.update(other_chart_table.prepare_discrete_data(other_view))
    terms_data.update(other_chart_table.prepare_terms_data(other_view))

    if request.user.is_authenticated():
        prefix = "user_"
        view = UserChartView(request, model=Chart, table_class=UserChartTable)
        user_chart_table = UserChartTable(view.get_table_data(prefix),
                                          prefix=prefix)
        config = RequestConfig(request,
                               paginate={"per_page": user_chart_table.length})
        config.configure(user_chart_table)
        search_data.update(user_chart_table.prepare_search_data(view))
        discrete_data.update(user_chart_table.prepare_discrete_data(view))
        terms_data.update(user_chart_table.prepare_terms_data(view))
    else:
        user_chart_table = None
    template = loader.get_template('lava_results_app/chart_list.html')
    return HttpResponse(template.render(
        {
            'user_chart_table': user_chart_table,
            'other_chart_table': other_chart_table,
            'search_data': search_data,
            "discrete_data": discrete_data,
            'terms_data': terms_data,
            'group_tables': group_tables,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(chart_list),
            'context_help': ['lava-queries-charts'],
        }, request=request)
    )


@BreadCrumb("Chart {name}", parent=chart_list,
            needs=['name'])
@login_required
def chart_display(request, name):

    chart = get_object_or_404(Chart, name=name)

    if not request.user.is_superuser:
        if not chart.is_published and chart.owner != request.user:
            raise PermissionDenied

    chart_data = {}
    for index, chart_query in enumerate(
            chart.chartquery_set.all().order_by('relative_index')):
        chart_data[index] = chart_query.get_data(request.user)
    template = loader.get_template('lava_results_app/chart_display.html')
    return HttpResponse(template.render(
        {
            'chart': chart,
            'chart_data': simplejson.dumps(chart_data),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                chart_display, name=name),
            'can_admin': chart.can_admin(request.user),
        }, request=request)
    )


@BreadCrumb("Custom Chart", parent=chart_list)
@login_required
def chart_custom(request):

    content_type = Query.get_content_type(request.GET.get("entity"))

    chart_type = request.GET.get("type")
    chart_type_choices = ChartQuery._meta.get_field_by_name(
        'chart_type')[0].choices
    if not chart_type:
        chart_type = ChartQuery._meta.get_field_by_name(
            'chart_type')[0].default
    else:
        found = False
        for choice in chart_type_choices:
            if chart_type in choice:
                found = True
        if not found:
            raise InvalidChartTypeError(
                "Wrong chart type param. Please refer to chart docs.")

    if content_type.model_class() not in QueryCondition.RELATION_MAP:
        raise InvalidContentTypeError(
            "Wrong table name in entity param. Please refer to chart docs.")

    if content_type.model_class() == TestCase and chart_type == "pass/fail":
        raise TestCasePassFailChartError(
            "Chart of TestCase entity cannot be of pass/fail chart type.")

    conditions = Query.parse_conditions(
        content_type, request.GET.get("conditions"))

    chart = Chart(name="Custom")
    chart_query = ChartQuery(id=0)
    chart_query.chart = chart
    chart_query.chart_type = chart_type
    chart_data = {}
    chart_data[0] = chart_query.get_data(request.user, content_type,
                                         conditions)
    template = loader.get_template('lava_results_app/chart_display.html')
    return HttpResponse(template.render(
        {
            'chart': chart,
            'chart_data': simplejson.dumps(chart_data),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                chart_custom),
            'can_admin': False,
        }, request=request)
    )


@BreadCrumb("Chart {name}", parent=chart_list,
            needs=['name'])
@login_required
@ownership_required
def chart_detail(request, name):

    chart = get_object_or_404(Chart, name=name)
    template = loader.get_template('lava_results_app/chart_detail.html')
    return HttpResponse(template.render(
        {
            'chart': chart,
            'chart_queries': chart.queries.all(),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                chart_detail, name=name),
            'context_help': ['lava-queries-charts'],
        }, request=request)
    )


@BreadCrumb("Add new", parent=chart_list)
@login_required
def chart_add(request):

    chart = Chart()
    chart.owner = request.user

    return chart_form(
        request,
        BreadCrumbTrail.leading_to(chart_add),
        instance=chart,
        query_id=request.GET.get("query_id"))


@BreadCrumb("Edit {name}", parent=chart_detail,
            needs=['name'])
@login_required
@ownership_required
def chart_edit(request, name):

    chart = get_object_or_404(Chart, name=name)

    return chart_form(
        request,
        BreadCrumbTrail.leading_to(chart_edit, name=name),
        instance=chart)


@login_required
@ownership_required
def chart_delete(request, name):

    chart = get_object_or_404(Chart, name=name)

    chart.delete()
    return HttpResponseRedirect(reverse(
        'lava.results.chart_list'))


@login_required
@ownership_required
def chart_toggle_published(request, name):

    chart = get_object_or_404(Chart, name=name)

    chart.is_published = not chart.is_published
    chart.save()

    return HttpResponseRedirect(chart.get_absolute_url() + "/+detail")


@login_required
def chart_group_list(request):

    term = request.GET['term']
    groups = [str(group.name) for group in ChartGroup.objects.filter(
        name__istartswith=term)]
    return HttpResponse(simplejson.dumps(groups),
                        content_type='application/json')


@login_required
def chart_add_group(request, name):

    if request.method != 'POST':
        raise PermissionDenied

    group_name = request.POST.get("value")
    chart = get_object_or_404(Chart, name=name)
    old_group = chart.chart_group

    if not group_name:
        chart.chart_group = None
    else:
        new_group = ChartGroup.objects.get_or_create(name=group_name)[0]
        chart.chart_group = new_group

    chart.save()

    if old_group:
        if not old_group.chart_set.count():
            old_group.delete()

    return HttpResponse(group_name, content_type='application/json')


@login_required
@ownership_required
def chart_select_group(request, name):

    if request.method != 'POST':
        raise PermissionDenied

    group_name = request.POST.get("value")
    chart = get_object_or_404(Chart, name=name)

    if not group_name:
        chart.group = None
    else:
        group = Group.objects.get(name=group_name)
        chart.group = group

    chart.save()

    return HttpResponse(group_name, content_type='application/json')


@login_required
def get_chart_group_names(request):

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


@BreadCrumb("Add chart query", parent=chart_detail, needs=['name'])
@login_required
@ownership_required
def chart_query_add(request, name):

    chart = get_object_or_404(Chart, name=name)

    return chart_query_form(
        request,
        BreadCrumbTrail.leading_to(chart_query_add, name=name),
        chart=chart
    )


@BreadCrumb("Edit chart query", parent=chart_detail, needs=['name', 'id'])
@login_required
@ownership_required
def chart_query_edit(request, name, id):

    chart_query = get_object_or_404(ChartQuery, id=id)

    return chart_query_form(
        request,
        BreadCrumbTrail.leading_to(chart_query_edit, name=name, id=id),
        instance=chart_query
    )


@login_required
@ownership_required
def chart_query_remove(request, name, id):

    chart_query = get_object_or_404(ChartQuery, id=id)
    chart = chart_query.chart
    chart_query.delete()

    return HttpResponseRedirect(chart.get_absolute_url() + "/+detail")


@login_required
@ownership_required
def chart_omit_result(request, name, id, result_id):

    chart_query = get_object_or_404(ChartQuery, id=id)
    result_object = get_object_or_404(
        chart_query.query.content_type.model_class(),
        id=result_id
    )

    try:
        QueryOmitResult.objects.create(query=chart_query.query,
                                       content_object=result_object)
    except IntegrityError:
        # Ignore unique constraint violation.
        pass

    return HttpResponseRedirect(chart_query.chart.get_absolute_url())


@login_required
def chart_query_order_update(request, name):

    if request.method != 'POST':
        raise PermissionDenied

    chart_query_order = request.POST.get("chart_query_order").split(",")
    chart = get_object_or_404(Chart, name=name)

    try:
        for index, chart_query_id in enumerate(chart_query_order):
            chart_query = ChartQuery.objects.get(pk=chart_query_id)
            chart_query.relative_index = index
            chart_query.save()
    except:
        return HttpResponse("fail", content_type='application/json')

    return HttpResponse("success", content_type='application/json')


@login_required
def settings_update(request, name, id):

    if request.method != 'POST':
        raise PermissionDenied

    try:
        instance = ChartQueryUser.objects.get(user=request.user,
                                              chart_query__id=id)
    except ChartQueryUser.DoesNotExist:
        # Create new.
        instance = ChartQueryUser()
        instance.chart_query_id = id
        instance.user = request.user

    form = ChartQueryUserForm(request.user, request.POST,
                              instance=instance)
    if form.is_valid():
        instance = form.save()
        data = serializers.serialize('json', [instance])
        return HttpResponse(data, content_type='application/json')
    else:
        return HttpResponseBadRequest()


def chart_form(request, bread_crumb_trail, instance=None, query_id=None):

    if request.method == 'POST':

        form = ChartForm(request.user, request.POST,
                         instance=instance)
        if form.is_valid():
            chart = form.save()
            if query_id:
                query = Query.objects.get(pk=query_id)
                chart_query = ChartQuery(chart=chart, query=query)
                chart_query.save()

            return HttpResponseRedirect(chart.get_absolute_url() + "/+detail")

    else:
        form = ChartForm(request.user, instance=instance)
        form.fields['owner'].initial = request.user
    template = loader.get_template('lava_results_app/chart_form.html')
    return HttpResponse(template.render(
        {
            'bread_crumb_trail': bread_crumb_trail,
            'form': form,
        }, request=request))


def chart_query_form(request, bread_crumb_trail, chart=None, instance=None):

    if request.method == 'POST':

        form = ChartQueryForm(request.user, request.POST,
                              instance=instance)
        if form.is_valid():
            chart_query = form.save()
            return HttpResponseRedirect(
                chart_query.chart.get_absolute_url() + "/+detail")

    else:
        form = ChartQueryForm(request.user, instance=instance)
        form.fields['chart'].initial = chart
    template = loader.get_template('lava_results_app/chart_query_form.html')
    return HttpResponse(template.render(
        {
            'bread_crumb_trail': bread_crumb_trail,
            'form': form,
            'instance': instance
        }, request=request))
