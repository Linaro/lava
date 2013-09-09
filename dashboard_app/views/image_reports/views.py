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

from dashboard_app.views.image_reports.forms import (
    ImageReportEditorForm,
    ImageReportChartForm,
    )

from dashboard_app.models import (
    ImageReport,
    ImageReportChart,
    )

from dashboard_app.views.filters.tables import AllFiltersSimpleTable

from dashboard_app.views import (
    index,
    )


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
            raise ValidationError(str(form.errors))


    form = ImageReportChartForm(request.user, instance=instance)
    if not instance:
        image_report_id = request.GET['image_report_id']
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
