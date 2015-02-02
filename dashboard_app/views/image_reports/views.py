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
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render_to_response
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
    ImageChartTestAttribute,
    ImageChartTestCase,
    ImageChartUser,
    ImageChartTestUser,
    ImageChartTestCaseUser,
    ImageChartTestAttributeUser,
    Test,
    TestCase,
    TestRunFilter,
)

from dashboard_app.views.image_reports.tables import (
    UserImageReportTable,
    OtherImageReportTable,
    GroupImageReportTable,
)
from django_tables2 import (
    RequestConfig,
)
from lava.utils.lavatable import LavaView


class UserImageReportView(LavaView):

    def get_queryset(self):
        return ImageReport.objects.filter(user=self.request.user).order_by('name')


class OtherImageReportView(LavaView):

    def get_queryset(self):
        # All public reports for authenticated users which are not part
        # of any group.
        # Only reports containing all public filters for non-authenticated.
        other_reports = ImageReport.objects.filter(is_published=True,
                                                   image_report_group=None).order_by('name')

        non_accessible_reports = []
        for report in other_reports:
            if not report.is_accessible_by(self.request.user):
                non_accessible_reports.append(report.id)

        if self.request and self.request.user.is_authenticated():
            return other_reports.exclude(id__in=non_accessible_reports)
        else:
            return other_reports.exclude(
                imagereportchart__imagechartfilter__filter__public=False,
                id__in=non_accessible_reports).order_by('name')


class GroupImageReportView(LavaView):

    def __init__(self, request, group, **kwargs):
        super(GroupImageReportView, self).__init__(request, **kwargs)
        self.image_report_group = group

    def get_queryset(self):
        # Specific group reports for authenticated users.
        # Only reports containing all public filters for non-authenticated.
        group_reports = ImageReport.objects.filter(
            is_published=True,
            image_report_group=self.image_report_group).order_by('name')

        non_accessible_reports = []
        for report in group_reports:
            if not report.is_accessible_by(self.request.user):
                non_accessible_reports.append(report.id)

        if self.request.user.is_authenticated():
            return group_reports.exclude(id__in=non_accessible_reports)
        else:
            return group_reports.exclude(
                imagereportchart__imagechartfilter__filter__public=False,
                id__in=non_accessible_reports).order_by('name')


@BreadCrumb("Image reports", parent=index)
def image_report_list(request):

    group_tables = {}
    terms_data = search_data = discrete_data = {}
    for group in ImageReportGroup.objects.all():
        if group.imagereport_set.count():
            prefix = "group_%s_" % group.id
            group_view = GroupImageReportView(request, group, model=ImageReportChart, table_class=GroupImageReportTable)
            table = GroupImageReportTable(group_view.get_table_data(prefix), prefix=prefix)
            search_data.update(table.prepare_search_data(group_view))
            discrete_data.update(table.prepare_discrete_data(group_view))
            terms_data.update(table.prepare_terms_data(group_view))
            group_tables[group.name] = table
            config = RequestConfig(request, paginate={"per_page": table.length})
            config.configure(table)

    prefix = "other_"
    other_view = OtherImageReportView(request, model=ImageReportChart, table_class=OtherImageReportTable)
    other_image_table = OtherImageReportTable(other_view.get_table_data(prefix), prefix=prefix)
    config = RequestConfig(request, paginate={"per_page": other_image_table.length})
    config.configure(other_image_table)
    search_data.update(other_image_table.prepare_search_data(other_view))
    discrete_data.update(other_image_table.prepare_discrete_data(other_view))
    terms_data.update(other_image_table.prepare_terms_data(other_view))

    if request.user.is_authenticated():
        prefix = "user_"
        view = UserImageReportView(request, model=ImageReportChart, table_class=UserImageReportTable)
        user_image_table = UserImageReportTable(view.get_table_data(prefix), prefix=prefix)
        config = RequestConfig(request, paginate={"per_page": user_image_table.length})
        config.configure(user_image_table)
        search_data.update(user_image_table.prepare_search_data(view))
        discrete_data.update(user_image_table.prepare_discrete_data(view))
        terms_data.update(user_image_table.prepare_terms_data(view))
    else:
        user_image_table = None

    return render_to_response(
        'dashboard_app/image_report_list.html', {
            'user_image_table': user_image_table,
            'other_image_table': other_image_table,
            'search_data': search_data,
            "discrete_data": discrete_data,
            'terms_data': terms_data,
            'group_tables': group_tables,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(image_report_list),
            'context_help': BreadCrumbTrail.leading_to(image_report_list),
        }, RequestContext(request)
    )


@BreadCrumb("Image report {name}", parent=image_report_list, needs=['name'])
@public_filters_or_login_required
def image_report_display(request, name):

    image_report = get_object_or_404(ImageReport, name=name)

    if not request.user.is_superuser:
        if not image_report.is_published and image_report.user != request.user:
            raise PermissionDenied

    if not image_report.is_accessible_by(request.user):
        raise PermissionDenied()

    chart_data = {}
    for chart in image_report.imagereportchart_set.all().order_by(
            'relative_index'):
        chart_data[chart.relative_index] = chart.get_chart_data(request.user)

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

    image_report = get_object_or_404(ImageReport, name=name)

    return render_to_response(
        'dashboard_app/image_report_detail.html', {
            'image_report': image_report,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                image_report_detail, name=name),
            'context_help': BreadCrumbTrail.leading_to(image_report_list),
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

    image_report = get_object_or_404(ImageReport, name=name)

    return image_report_form(
        request,
        BreadCrumbTrail.leading_to(image_report_edit,
                                   name=name),
        instance=image_report)


@login_required
@ownership_required
def image_report_delete(request, name):

    image_report = get_object_or_404(ImageReport, name=name)
    image_report.delete()
    return HttpResponseRedirect(reverse(
        'lava.dashboard.image_report.report_list'))


@login_required
@ownership_required
def image_report_publish(request, name):

    image_report = get_object_or_404(ImageReport, name=name)

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

    image_report = get_object_or_404(ImageReport, name=name)
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


@BreadCrumb("Image chart", parent=image_report_detail,
            needs=['name', 'id'])
@ownership_required
def image_chart_detail(request, name, id):

    image_chart = get_object_or_404(ImageReportChart, id=id)

    xaxis_attribute_changed = False
    supported_attrs = image_chart.get_supported_attributes(request.user)
    if image_chart.xaxis_attribute:
        if not supported_attrs or \
           image_chart.xaxis_attribute not in supported_attrs:
            image_chart.xaxis_attribute = None
            image_chart.save()
            xaxis_attribute_changed = True

    return render_to_response(
        'dashboard_app/image_report_chart_detail.html', {
            'image_chart': image_chart,
            'xaxis_attribute_changed': xaxis_attribute_changed,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                image_chart_detail, name=name, id=id),
        }, RequestContext(request)
    )


@BreadCrumb("Add chart", parent=image_report_detail, needs=['name'])
@login_required
@ownership_required
def image_chart_add(request, name):

    image_report = get_object_or_404(ImageReport, name=name)
    return image_chart_form(
        request,
        BreadCrumbTrail.leading_to(image_chart_add, name=name),
        image_report=image_report)


@BreadCrumb("Update", parent=image_chart_detail, needs=['name', 'id'])
@login_required
@ownership_required
def image_chart_edit(request, name, id):

    image_chart = get_object_or_404(ImageReportChart, id=id)
    return image_chart_form(
        request,
        BreadCrumbTrail.leading_to(image_chart_edit, name=name, id=id),
        instance=image_chart)


@login_required
@ownership_required
def image_chart_delete(request, name, id):

    image_chart = get_object_or_404(ImageReportChart, id=id)
    image_chart.delete()
    return HttpResponseRedirect(
        reverse('image_report_detail',
                kwargs={"name": image_chart.image_report.name}))


@login_required
def image_report_group_list(request):

    term = request.GET['term']
    groups = [str(group.name) for group in ImageReportGroup.objects.filter(
        name__istartswith=term)]
    return HttpResponse(simplejson.dumps(groups), content_type='application/json')


@login_required
def image_report_add_group(request, name):

    if request.method != 'POST':
        raise PermissionDenied

    group_name = request.POST.get("value")
    image_report = get_object_or_404(ImageReport, name=name)
    old_group = image_report.image_report_group

    if not group_name:
        image_report.image_report_group = None
    else:
        new_group = ImageReportGroup.objects.get_or_create(name=group_name)[0]
        image_report.image_report_group = new_group

    image_report.save()

    if old_group:
        if not old_group.imagereport_set.count():
            old_group.delete()

    return HttpResponse(group_name, content_type='application/json')


@login_required
def image_report_order_update(request, name):

    if request.method != 'POST':
        raise PermissionDenied

    chart_id_order = request.POST.get("chart_id_order").split(",")
    image_report = get_object_or_404(ImageReport, name=name)

    try:
        for index, chart_id in enumerate(chart_id_order):
            image_chart = ImageReportChart.objects.get(pk=chart_id)
            image_chart.relative_index = index
            image_chart.save()
    except:
        return HttpResponse("fail", content_type='application/json')

    return HttpResponse("success", content_type='application/json')


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

    # Update the chart test/test case user table with hidden test ids.
    try:
        chart = ImageReportChart.objects.get(id=id)
        if chart.chart_type == "pass/fail":

            chart_test = ImageChartTest.objects.get(
                id=request.POST["visible_chart_test_id"])

            chart_test_user = ImageChartTestUser.objects.get_or_create(
                user=request.user,
                image_chart_test=chart_test)[0]

            chart_test_user.is_visible = not chart_test_user.is_visible
            chart_test_user.save()

        elif chart.chart_type == "measurement":
            chart_test_case = ImageChartTestCase.objects.get(
                id=request.POST["visible_chart_test_id"])

            chart_test_user = ImageChartTestCaseUser.objects.get_or_create(
                user=request.user,
                image_chart_test_case=chart_test_case)[0]

            chart_test_user.is_visible = not chart_test_user.is_visible
            chart_test_user.save()

        elif chart.chart_type == "attributes":

            chart_test = ImageChartTest.objects.get(
                id=request.POST["visible_chart_test_id"])

            chart_test_attribute = ImageChartTestAttribute.objects.get(
                image_chart_test=chart_test,
                name=request.POST["visible_attribute_name"]
            )

            attribute_user = ImageChartTestAttributeUser.objects.get_or_create(
                user=request.user,
                image_chart_test_attribute=chart_test_attribute)[0]

            attribute_user.is_visible = not attribute_user.is_visible
            attribute_user.save()

    except Exception as e:
        # Don't update the chart test/test case user table.
        pass

    form = ImageChartUserForm(request.user, request.POST,
                              instance=instance)
    if form.is_valid():
        instance = form.save()
        data = serializers.serialize('json', [instance])
        return HttpResponse(data, content_type='application/json')
    else:
        return HttpResponseBadRequest()


@login_required
def image_chart_filter_type_check(request):
    # Check if current filter has build number comparing to all other filters
    # already related to this image chart.

    if request.method != 'POST':
        raise PermissionDenied

    chart_id = request.POST.get("chart_id")
    filter_id = request.POST.get("filter_id")
    image_chart = get_object_or_404(ImageReportChart, id=chart_id)
    filter = get_object_or_404(TestRunFilter, id=filter_id)

    has_build_attribute = True if filter.build_number_attribute else False

    for chart_filter in image_chart.imagechartfilter_set.all():
        has_attribute_each = False
        if chart_filter.filter.build_number_attribute:
            has_attribute_each = True

        if has_attribute_each != has_build_attribute:
            return HttpResponse(simplejson.dumps({"result": "False"}),
                                content_type='application/json')

    return HttpResponse(simplejson.dumps({"result": "True"}),
                        content_type='application/json')


@login_required
def get_chart_test_data(request):

    chart_test = _get_image_chart_test(request.GET.get('chart_filter_id'),
                                       request.GET.get('chart_test_id'))

    data = chart_test.__dict__.copy()
    data.pop("_state", None)
    data["test_name"] = chart_test.test_name
    data["attributes"] = chart_test.attributes
    data["all_attributes"] = chart_test.get_available_attributes(request.user)
    return HttpResponse(simplejson.dumps([data]), content_type='application/json')


@public_filters_or_login_required
def image_chart_export(request, name, id):
    # Create and serve the CSV file.

    chart = get_object_or_404(ImageReportChart, id=id)
    chart_data = chart.get_chart_data(request.user)

    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, "%s.csv" % chart.name)

    chart_data_keys = []
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
        response = HttpResponse(content_type='text/csv')
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

    return render_to_response(
        'dashboard_app/image_report_chart_form.html', {
            'bread_crumb_trail': bread_crumb_trail,
            'form': form,
        }, RequestContext(request))


@BreadCrumb("Add filter", parent=image_chart_detail,
            needs=['name', 'id'])
def image_chart_filter_add(request, name, id):
    image_chart = get_object_or_404(ImageReportChart, id=id)
    return image_chart_filter_form(
        request,
        BreadCrumbTrail.leading_to(image_chart_filter_add, name=name, id=id),
        chart_instance=image_chart)


@BreadCrumb("Image chart filter", parent=image_chart_detail,
            needs=['name', 'id', 'slug'])
@ownership_required
def image_chart_filter_detail(request, name, id, slug):

    if request.method == 'POST':
        # Saving image chart test.
        chart_test = _get_image_chart_test(
            slug,
            request.POST.get('chart_test_id'))

        request.POST.get('attributes')
        chart_test.name = request.POST.get('alias')
        chart_test.attributes = request.POST.getlist('attributes')
        chart_test.save()

    chart_filter = get_object_or_404(ImageChartFilter, id=slug)

    image_chart = chart_filter.image_chart
    xaxis_attribute_changed = False
    supported_attrs = image_chart.get_supported_attributes(request.user)
    if image_chart.xaxis_attribute:
        if not supported_attrs or \
           image_chart.xaxis_attribute not in supported_attrs:
            image_chart.xaxis_attribute = None
            image_chart.save()
            xaxis_attribute_changed = True

    return render_to_response(
        'dashboard_app/image_chart_filter_detail.html', {
            'chart_filter': chart_filter,
            'xaxis_attribute_changed': xaxis_attribute_changed,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                image_chart_filter_detail, name=name, id=id, slug=slug),
        }, RequestContext(request)
    )


@BreadCrumb("Edit", parent=image_chart_filter_detail,
            needs=['name', 'id', 'slug'])
@login_required
def image_chart_filter_edit(request, name, id, slug):
    image_chart_filter = get_object_or_404(ImageChartFilter, id=slug)
    return image_chart_filter_form(
        request,
        BreadCrumbTrail.leading_to(image_chart_filter_edit, name=name, id=id,
                                   slug=slug),
        instance=image_chart_filter)


@BreadCrumb("Image chart delete filter", parent=image_report_list)
def image_chart_filter_delete(request, name, id, slug):
    image_chart_filter = get_object_or_404(ImageChartFilter, id=slug)
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

            if not chart_filter.is_all_tests_included:
                if chart_filter.image_chart.chart_type != 'measurement':

                    image_chart_tests = Test.objects.filter(
                        imagecharttest__image_chart_filter=chart_filter).order_by('id')

                    tests = form.cleaned_data['image_chart_tests']

                    for test in tests:
                        if test in image_chart_tests:
                            chart_test = ImageChartTest.objects.get(
                                image_chart_filter=chart_filter, test=test)
                            chart_test.save()
                        else:
                            chart_test = ImageChartTest()
                            chart_test.image_chart_filter = chart_filter
                            chart_test.test = test
                            chart_test.save()

                    for chart_test in image_chart_tests:
                        if chart_test not in tests:
                            ImageChartTest.objects.get(
                                image_chart_filter=chart_filter,
                                test=chart_test).delete()

                else:

                    image_chart_test_cases = TestCase.objects.filter(
                        imagecharttestcase__image_chart_filter=chart_filter
                    ).order_by('id')

                    test_cases = form.cleaned_data['image_chart_test_cases']

                    for test_case in test_cases:
                        if test_case in image_chart_test_cases:
                            chart_test_case = ImageChartTestCase.objects.get(
                                image_chart_filter=chart_filter,
                                test_case=test_case)
                            chart_test_case.save()
                        else:
                            chart_test_case = ImageChartTestCase()
                            chart_test_case.image_chart_filter = chart_filter
                            chart_test_case.test_case = test_case
                            chart_test_case.save()

                    for chart_test_case in image_chart_test_cases:
                        if chart_test_case not in test_cases:
                            ImageChartTestCase.objects.get(
                                image_chart_filter=chart_filter,
                                test_case=chart_test_case).delete()

            return HttpResponseRedirect(
                chart_filter.get_absolute_url())

    else:
        form = ImageChartFilterForm(request.user, instance=instance,
                                    initial={'image_chart': chart_instance})

    return render_to_response(
        'dashboard_app/image_chart_filter_form.html', {
            'bread_crumb_trail': bread_crumb_trail,
            'image_chart': chart_instance,
            'instance': instance,
            'form': form,
        }, RequestContext(request))


def _get_image_chart_test(chart_filter_id, chart_test_id):
    # Returns either ImageChartTest or ImageChartTestCase object.
    # Raises ImageChartTestCase.DoesNotExist if this chart test does not exist.
    try:
        chart_test = ImageChartTest.objects.get(
            image_chart_filter__id=chart_filter_id,
            id=chart_test_id)
    except:
        chart_test = ImageChartTestCase.objects.get(
            image_chart_filter__id=chart_filter_id,
            id=chart_test_id)

    return chart_test
