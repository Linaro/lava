# Copyright (C) 2010-2013 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
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

import csv
import os
import simplejson
import tempfile

from django.contrib.auth.decorators import login_required
from django.core import serializers
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.safestring import mark_safe

from lava_server.bread_crumbs import (
    BreadCrumb,
    BreadCrumbTrail,
)

from dashboard_app.views import index
from dashboard_app.views.image_reports.decorators import (
    ownership_required,
    public_filters_or_login_required,
)

from dashboard_app.views.image_reports.forms import (
    ImageReportEditorForm,
    ImageReportChartForm,
    ImageChartFilterForm,
    ImageChartUserForm,
)

from dashboard_app.models import (
    ImageReport,
    ImageReportGroup,
    ImageReportChart,
    ImageChartFilter,
    ImageChartTest,
    ImageChartTestCase,
    ImageChartUser,
    Test,
    TestCase,
    TestRunFilter,
)

from dashboard_app.views.image_reports.tables import (
    UserImageReportTable,
    OtherImageReportTable,
    GroupImageReportTable,
)

from dashboard_app.views.filters.tables import AllFiltersSimpleTable


@BreadCrumb("Image reports", parent=index)
def image_report_list(request):

    image_reports = ImageReport.objects.all()

    reports_group = ImageReportGroup.objects.all()
    group_tables = {}
    for group in reports_group:
        if group.imagereport_set.count():
            group_tables[group.name] = GroupImageReportTable(
                "group-table-%s" % group.id, "group-table-%s" % group.id,
                params=(request.user, group))

    other_image_table = OtherImageReportTable("other-image-reports", None,
                                              params=(request.user,))

    if request.user.is_authenticated():
        user_image_table = UserImageReportTable("user-image-reports", None,
                                                params=(request.user,))
    else:
        user_image_table = None

    return render_to_response(
        'dashboard_app/image_report_list.html', {
            'user_image_table': user_image_table,
            'other_image_table': other_image_table,
            'group_tables': group_tables,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                image_report_list),
        }, RequestContext(request)
    )


@BreadCrumb("Image report {name}", parent=image_report_list, needs=['name'])
@public_filters_or_login_required
def image_report_display(request, name):

    image_report = ImageReport.objects.get(name=name)

    if not image_report.is_published and image_report.user != request.user:
        raise PermissionDenied

    chart_data = {}
    for chart in image_report.imagereportchart_set.all():
        chart_data[chart.id] = chart.get_chart_data(request.user)

    return render_to_response(
        'dashboard_app/image_report_display.html', {
            'image_report': image_report,
            'chart_data': simplejson.dumps(chart_data),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                image_report_detail, name=name),
        }, RequestContext(request)
    )


@BreadCrumb("Image report {name}", parent=image_report_list, needs=['name'])
@login_required
@ownership_required
def image_report_detail(request, name):

    image_report = ImageReport.objects.get(name=name)

    return render_to_response(
        'dashboard_app/image_report_detail.html', {
            'image_report': image_report,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                image_report_detail, name=name),
        }, RequestContext(request)
    )


@BreadCrumb("Add new", parent=image_report_list)
@login_required
def image_report_add(request):

    return image_report_form(
        request,
        BreadCrumbTrail.leading_to(image_report_add))


@BreadCrumb("Edit", parent=image_report_detail,
            needs=['name'])
@login_required
@ownership_required
def image_report_edit(request, name):

    image_report = ImageReport.objects.get(name=name)

    return image_report_form(
        request,
        BreadCrumbTrail.leading_to(image_report_edit,
                                   name=name),
        instance=image_report)


@login_required
@ownership_required
def image_report_delete(request, name):

    image_report = ImageReport.objects.get(name=name)
    image_report.delete()
    return HttpResponseRedirect(reverse('image_report_list'))


@login_required
@ownership_required
def image_report_publish(request, name):

    image_report = ImageReport.objects.get(name=name)
    image_report.is_published = True
    image_report.save()

    return render_to_response(
        'dashboard_app/image_report_detail.html', {
            'image_report': image_report,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                image_report_detail, name=name),
        }, RequestContext(request)
    )


@login_required
@ownership_required
def image_report_unpublish(request, name):

    image_report = ImageReport.objects.get(name=name)
    image_report.is_published = False
    image_report.save()

    return render_to_response(
        'dashboard_app/image_report_detail.html', {
            'image_report': image_report,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                image_report_detail, name=name),
        }, RequestContext(request)
    )


def image_report_form(request, bread_crumb_trail, instance=None):

    if request.method == 'POST':

        form = ImageReportEditorForm(request.user, request.POST,
                                     instance=instance)
        if form.is_valid():
            image_report = form.save()
            return HttpResponseRedirect(image_report.get_absolute_url()
                                        + "/+detail")

    else:
        form = ImageReportEditorForm(request.user, instance=instance)
        form.fields['user'].initial = request.user

    return render_to_response(
        'dashboard_app/image_report_form.html', {
            'bread_crumb_trail': bread_crumb_trail,
            'form': form,
        }, RequestContext(request))


@BreadCrumb("Image chart", parent=image_report_detail, needs=['name', 'id'])
@ownership_required
def image_chart_detail(request, name, id):

    image_chart = ImageReportChart.objects.get(id=id)

    return render_to_response(
        'dashboard_app/image_report_chart_detail.html', {
            'image_chart': image_chart,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                image_chart_detail, name=name, id=id),
        }, RequestContext(request)
    )


@BreadCrumb("Add chart", parent=image_report_detail, needs=['name'])
@login_required
@ownership_required
def image_chart_add(request, name):

    image_report = ImageReport.objects.get(name=name)
    return image_chart_form(
        request,
        BreadCrumbTrail.leading_to(image_chart_add, name=name),
        image_report=image_report)


@BreadCrumb("Update", parent=image_chart_detail, needs=['name', 'id'])
@login_required
@ownership_required
def image_chart_edit(request, name, id):

    image_chart = ImageReportChart.objects.get(id=id)
    return image_chart_form(
        request,
        BreadCrumbTrail.leading_to(image_chart_edit, name=name, id=id),
        instance=image_chart)


@login_required
@ownership_required
def image_chart_delete(request, name, id):

    image_chart = ImageReportChart.objects.get(id=id)
    image_chart.delete()
    return HttpResponseRedirect(
        reverse('image_report_detail',
                kwargs={"name": image_chart.image_report.name}))


@login_required
def image_report_group_list(request):

    term = request.GET['term']
    groups = [str(group.name) for group in ImageReportGroup.objects.filter(
        name__istartswith=term)]
    return HttpResponse(simplejson.dumps(groups), mimetype='application/json')


@login_required
def image_report_add_group(request, name):

    if request.method != 'POST':
        raise PermissionDenied

    image_report = ImageReport.objects.get(name=name)
    image_report.image_report_group = ImageReportGroup.objects.get_or_create(
        name=request.POST.get("value"))[0]
    image_report.save()
    return HttpResponse(request.POST.get("value"), mimetype='application/json')


@login_required
def image_chart_settings_update(request, name, id):

    if request.method != 'POST':
        raise PermissionDenied

    try:
        instance = ImageChartUser.objects.get(user=request.user,
                                              image_chart__id=id)
    except ImageChartUser.DoesNotExist:
        # Create new.
        instance = ImageChartUser()
        instance.image_chart_id = id
        instance.user = request.user

    form = ImageChartUserForm(request.user, request.POST,
                              instance=instance)
    if form.is_valid():
        instance = form.save()
        data = serializers.serialize('json', [instance])
        return HttpResponse(data, mimetype='application/json')


@public_filters_or_login_required
def image_chart_export(request, name, id):
    # Create and serve the CSV file.

    chart = ImageReportChart.objects.get(id=id)
    chart_data = chart.get_chart_data(request.user)

    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, "%s.csv" % chart.name)

    for chart_item in chart_data["test_data"]:
        chart_data_keys = chart_item.keys()
        break

    chart_data_keys.sort()
    # One column which is not relevant for CSV file.
    if "filter_rep" in chart_data_keys:
        chart_data_keys.remove("filter_rep")

    with open(file_path, 'w+') as csv_file:
        out = csv.DictWriter(csv_file, quoting=csv.QUOTE_ALL,
                             extrasaction='ignore',
                             fieldnames=chart_data_keys)
        out.writeheader()
        for chart_item in chart_data["test_data"]:
            out.writerow(chart_item)

    with open(file_path, 'r') as csv_file:
        response = HttpResponse(mimetype='text/csv')
        response['Content-Disposition'] = "attachment; filename=%s.csv" % \
                                          chart.name
        response.write(csv_file.read())
        return response


def image_chart_form(request, bread_crumb_trail, instance=None,
                     image_report=None):

    if request.method == 'POST':

        form = ImageReportChartForm(request.user, request.POST,
                                    instance=instance)
        if form.is_valid():
            image_chart = form.save()
            return HttpResponseRedirect(
                image_chart.get_absolute_url())

    else:
        form = ImageReportChartForm(request.user, instance=instance)
        form.fields['image_report'].initial = image_report

    filters_table = AllFiltersSimpleTable("all-filters", None)

    return render_to_response(
        'dashboard_app/image_report_chart_form.html', {
            'bread_crumb_trail': bread_crumb_trail,
            'form': form,
            'filters_table': filters_table,
        }, RequestContext(request))


@BreadCrumb("Add filter", parent=image_chart_detail,
            needs=['name', 'id'])
def image_chart_filter_add(request, name, id):
    image_chart = ImageReportChart.objects.get(id=id)
    return image_chart_filter_form(
        request,
        BreadCrumbTrail.leading_to(image_chart_filter_add, name=name, id=id),
        chart_instance=image_chart)


@BreadCrumb("Update image chart filter", parent=image_report_list)
@login_required
def image_chart_filter_edit(request, id):
    image_chart_filter = ImageChartFilter.objects.get(id=id)
    return image_chart_filter_form(
        request,
        BreadCrumbTrail.leading_to(image_chart_filter_edit, id=id),
        instance=image_chart_filter)


@BreadCrumb("Image chart add filter", parent=image_report_list)
def image_chart_filter_delete(request, id):
    image_chart_filter = ImageChartFilter.objects.get(id=id)
    url = image_chart_filter.image_chart.get_absolute_url()
    image_chart_filter.delete()
    return HttpResponseRedirect(url)


def image_chart_filter_form(request, bread_crumb_trail, chart_instance=None,
                            instance=None):

    if instance:
        chart_instance = instance.image_chart

    if request.method == 'POST':

        form = ImageChartFilterForm(request.user, request.POST,
                                    instance=instance)

        if form.is_valid():

            chart_filter = form.save()
            aliases = request.POST.getlist('aliases')

            if chart_filter.image_chart.chart_type == 'pass/fail':

                image_chart_tests = Test.objects.filter(
                    imagecharttest__image_chart_filter=chart_filter).order_by(
                    'id')

                tests = form.cleaned_data['image_chart_tests']

                for index, test in enumerate(tests):
                    if test in image_chart_tests:
                        chart_test = ImageChartTest.objects.get(
                            image_chart_filter=chart_filter, test=test)
                        chart_test.name = aliases[index]
                        chart_test.save()
                    else:
                        chart_test = ImageChartTest()
                        chart_test.image_chart_filter = chart_filter
                        chart_test.test = test
                        chart_test.name = aliases[index]
                        chart_test.save()

                for index, chart_test in enumerate(image_chart_tests):
                    if chart_test not in tests:
                        ImageChartTest.objects.get(
                            image_chart_filter=chart_filter,
                            test=chart_test).delete()

                return HttpResponseRedirect(
                    chart_filter.image_chart.get_absolute_url())

            else:

                image_chart_test_cases = TestCase.objects.filter(
                    imagecharttestcase__image_chart_filter=chart_filter
                ).order_by('id')

                test_cases = form.cleaned_data['image_chart_test_cases']

                for index, test_case in enumerate(test_cases):
                    if test_case in image_chart_test_cases:
                        chart_test_case = ImageChartTestCase.objects.get(
                            image_chart_filter=chart_filter,
                            test_case=test_case)
                        chart_test_case.name = aliases[index]
                        chart_test_case.save()
                    else:
                        chart_test_case = ImageChartTestCase()
                        chart_test_case.image_chart_filter = chart_filter
                        chart_test_case.test_case = test_case
                        chart_test_case.name = aliases[index]
                        chart_test_case.save()

                for index, chart_test_case in enumerate(
                        image_chart_test_cases):
                    if chart_test_case not in test_cases:
                        ImageChartTestCase.objects.get(
                            image_chart_filter=chart_filter,
                            test_case=chart_test_case).delete()

                return HttpResponseRedirect(
                    chart_filter.image_chart.get_absolute_url())

    else:
        form = ImageChartFilterForm(request.user, instance=instance,
                                    initial={'image_chart': chart_instance})

    filters_table = AllFiltersSimpleTable("all-filters", None)

    return render_to_response(
        'dashboard_app/image_chart_filter_form.html', {
            'bread_crumb_trail': bread_crumb_trail,
            'filters_table': filters_table,
            'image_chart': chart_instance,
            'instance': instance,
            'form': form,
        }, RequestContext(request))
