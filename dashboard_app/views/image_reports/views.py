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

from dashboard_app.models import ImageReport

from dashboard_app.views import (
    index,
    )


@BreadCrumb("Image reports", parent=index)
def image_reports_list(request):

    if request.user.is_authenticated():
        image_reports = ImageReport.objects.all()
    else:
        image_reports = None

    return render_to_response(
        'dashboard_app/image-report-list.html', {
            "image_reports": image_reports,
        }, RequestContext(request)
    )

@BreadCrumb("Add new filter", parent=image_reports_list)
@login_required
def image_report_add(request):
    return image_report_form(
        request,
        BreadCrumbTrail.leading_to(image_report_add))


def image_report_form(request, bread_crumb_trail, instance=None):
    if request.method == 'POST':
        return render_to_response('dashboard_app/image-report-list.html',
                                  {}, RequestContext(request))
    else:
        form = ImageReportEditorForm(request.user, instance=instance)

    return render_to_response(
        'dashboard_app/image-report-add.html', {
            'bread_crumb_trail': bread_crumb_trail,
            'form': form,
        }, RequestContext(request))

