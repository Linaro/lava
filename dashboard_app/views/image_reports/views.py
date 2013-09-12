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

import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.safestring import mark_safe

from lava_server.bread_crumbs import (
    BreadCrumb,
    BreadCrumbTrail,
)

from dashboard_app.views import index

from dashboard_app.views.image_reports.forms import (
    ImageReportEditorForm,
    ImageReportChartForm,
    ImageChartFilterForm,
    )

from dashboard_app.models import (
    ImageReport,
    ImageReportChart,
    ImageChartFilter,
    ImageChartTest,
    ImageChartTestCase,
    Test,
    TestCase,
    TestRunFilter,
    )

from dashboard_app.views.filters.tables import AllFiltersSimpleTable



@BreadCrumb("Image reports", parent=index)
def image_report_list(request):

    if request.user.is_authenticated():
        image_reports = ImageReport.objects.all()
    else:
        image_reports = None

    return render_to_response(
        'dashboard_app/image_report_list.html', {
            "image_reports": image_reports,
        }, RequestContext(request)
    )

@BreadCrumb("Image report {name}", parent=image_report_list, needs=['name'])
def image_report_detail(request, name):
    image_report = ImageReport.objects.get(name=name)

    return render_to_response(
        'dashboard_app/image_report_detail.html', {
            'image_report': image_report,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                image_report_detail, name=name),
        }, RequestContext(request)
    )

@BreadCrumb("Add new image report", parent=image_report_list)
@login_required
def image_report_add(request):
    return image_report_form(
        request,
        BreadCrumbTrail.leading_to(image_report_add))

@BreadCrumb("Update image report {name}", parent=image_report_list,
            needs=['name'])
@login_required
def image_report_edit(request, name):
    image_report = ImageReport.objects.get(name=name)
    return image_report_form(
        request,
        BreadCrumbTrail.leading_to(image_report_edit,
                                   name=name),
        instance=image_report)

@BreadCrumb("Publish image report {name}", parent=image_report_list,
            needs=['name'])
@login_required
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

@BreadCrumb("Unpublish image report {name}", parent=image_report_list,
            needs=['name'])
@login_required
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
            return HttpResponseRedirect(image_report.get_absolute_url())

    else:
        form = ImageReportEditorForm(request.user, instance=instance)

    return render_to_response(
        'dashboard_app/image_report_form.html', {
            'bread_crumb_trail': bread_crumb_trail,
            'form': form,
        }, RequestContext(request))

@BreadCrumb("Image chart details", parent=image_report_list)
def image_chart_detail(request, id):
    image_chart = ImageReportChart.objects.get(id=id)

    return render_to_response(
        'dashboard_app/image_report_chart_detail.html', {
            'image_chart': image_chart,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                image_chart_detail, id=id),
        }, RequestContext(request)
    )

@BreadCrumb("Add new image chart", parent=image_report_list)
@login_required
def image_chart_add(request):
    return image_chart_form(
        request,
        BreadCrumbTrail.leading_to(image_chart_add))

@BreadCrumb("Update image chart", parent=image_report_list)
@login_required
def image_chart_edit(request, id):
    image_chart = ImageReportChart.objects.get(id=id)
    return image_chart_form(
        request,
        BreadCrumbTrail.leading_to(image_chart_edit,
                                   id=id),
        instance=image_chart)

def image_chart_form(request, bread_crumb_trail, instance=None):

    if request.method == 'POST':

        form = ImageReportChartForm(request.user, request.POST,
                                    instance=instance)
        if form.is_valid():
            image_chart = form.save()
            return HttpResponseRedirect(
                image_chart.image_report.get_absolute_url())

    else:
        form = ImageReportChartForm(request.user, instance=instance)

    if not instance:
        image_report_id = request.GET.get('image_report_id', None)
    else:
        image_report_id = instance.image_report.id

    filters_table = AllFiltersSimpleTable("all-filters", None)

    return render_to_response(
        'dashboard_app/image_report_chart_form.html', {
            'bread_crumb_trail': bread_crumb_trail,
            'form': form,
            'filters_table': filters_table,
            'image_report_id': image_report_id,
        }, RequestContext(request))

@BreadCrumb("Image chart add filter", parent=image_report_list)
def image_chart_filter_add(request, id):
    image_chart = ImageReportChart.objects.get(id=id)
    return image_chart_filter_form(
        request,
        BreadCrumbTrail.leading_to(image_chart_filter_add),
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

            ImageChartTest.objects.filter(
                image_chart_filter=chart_filter).delete()
            ImageChartTestCase.objects.filter(
                image_chart_filter=chart_filter).delete()

            if chart_filter.image_chart.chart_type == 'pass/fail':

                tests = form.cleaned_data['image_chart_tests']
                aliases = request.POST.getlist('aliases')

                for index, test in enumerate(tests):
                    chart_test = ImageChartTest()
                    chart_test.image_chart_filter = chart_filter
                    chart_test.test = test
                    chart_test.name = aliases[index]
                    chart_test.save()

                return HttpResponseRedirect(
                    chart_filter.image_chart.get_absolute_url())

            else:
                test_cases = form.cleaned_data['image_chart_test_cases']
                for test_case in test_cases:
                    chart_test_case = ImageChartTestCase()
                    chart_test_case.image_chart_filter = chart_filter
                    chart_test_case.test_case = test_case
                    chart_test_case.save()

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
