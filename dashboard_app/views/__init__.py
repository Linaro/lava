# Copyright (C) 2010-2012 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
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

"""
Views for the Dashboard application
"""

import re
import json

from django.contrib.auth.decorators import login_required
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django.db.models.manager import Manager
from django.db.models.query import QuerySet
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response, redirect, get_object_or_404
from django.template import RequestContext, loader
from django.utils.safestring import mark_safe
from django.views.generic.list_detail import object_list, object_detail

from django_tables2 import Attrs, Column, TemplateColumn

from lava.utils.data_tables.tables import DataTablesTable
from lava_server.views import index as lava_index
from lava_server.bread_crumbs import (
    BreadCrumb,
    BreadCrumbTrail,
)

from dashboard_app.models import (
    Attachment,
    Bundle,
    BundleStream,
    DataReport,
    DataView,
    Tag,
    Test,
    TestResult,
    TestRun,
    TestingEffort,
)


def _get_queryset(klass):
    """
    Returns a QuerySet from a Model, Manager, or QuerySet. Created to make
    get_object_or_404 and get_list_or_404 more DRY.
    """
    if isinstance(klass, QuerySet):
        return klass
    elif isinstance(klass, Manager):
        manager = klass
    else:
        manager = klass._default_manager
    return manager.all()


def get_restricted_object_or_404(klass, via, user, *args, **kwargs):
    """
    Uses get() to return an object, or raises a Http404 exception if the object
    does not exist. If the object exists access control check is made
    using the via callback (via is called with the found object and the return
    value must be a RestrictedResource subclass.

    klass may be a Model, Manager, or QuerySet object. All other passed
    arguments and keyword arguments are used in the get() query.

    Note: Like with get(), an MultipleObjectsReturned will be raised if more than one
    object is found.
    """
    queryset = _get_queryset(klass)
    try:
        obj = queryset.get(*args, **kwargs)
        ownership_holder = via(obj)
        if not ownership_holder.is_accessible_by(user):
            raise queryset.model.DoesNotExist()
        return obj
    except queryset.model.DoesNotExist:
        raise Http404('No %s matches the given query.' % queryset.model._meta.object_name)


@BreadCrumb("Dashboard", parent=lava_index)
def index(request):
    return render_to_response(
        "dashboard_app/index.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(index)
        }, RequestContext(request))




class BundleStreamTable(DataTablesTable):

    pathname = TemplateColumn(
        '<a href="{% url dashboard_app.views.bundle_list record.pathname %}">'
        '<code>{{ record.pathname }}</code></a>')
    name = TemplateColumn(
        '{{ record.name|default:"<i>not set</i>" }}')
    number_of_test_runs = TemplateColumn(
        '<a href="{% url dashboard_app.views.test_run_list record.pathname %}">'
        '{{ record.get_test_run_count }}')
    number_of_bundles = TemplateColumn(
        '<a href="{% url dashboard_app.views.bundle_list record.pathname %}">'
        '{{ record.bundles.count}}</a>')

    def get_queryset(self, user):
        return BundleStream.objects.accessible_by_principal(user)

    datatable_opts = {
        'iDisplayLength': 25,
        'sPaginationType': "full_numbers",
        }

    searchable_columns = ['pathname', 'name']


def bundle_stream_list_json(request):
    return BundleStreamTable.json(request, params=(request.user,))


@BreadCrumb("Bundle Streams", parent=index)
def bundle_stream_list(request):
    """
    List of bundle streams.
    """
    return render_to_response(
        'dashboard_app/bundle_stream_list.html', {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                bundle_stream_list),
            "bundle_stream_table": BundleStreamTable(
                'bundle-stream-table', reverse(bundle_stream_list_json),
                params=(request.user,)),
            'has_personal_streams': (
                request.user.is_authenticated() and
                BundleStream.objects.filter(user=request.user).count() > 0),
            'has_team_streams': (
                request.user.is_authenticated() and
                BundleStream.objects.filter(
                    group__in = request.user.groups.all()).count() > 0),
        }, RequestContext(request)
    )


class BundleTable(DataTablesTable):

    content_filename = TemplateColumn(
        '<a href="{{ record.get_absolute_url }}">'
        '<code>{{ record.content_filename }}</code></a>',
        verbose_name="bundle name")

    passes = TemplateColumn('{{ record.get_summary_results.pass|default:"0" }}')
    fails = TemplateColumn('{{ record.get_summary_results.fail|default:"0" }}')
    total_results = TemplateColumn('{{ record.get_summary_results.total }}')

    uploaded_on = TemplateColumn('{{ record.uploaded_on|date:"Y-m-d H:i:s"}}')
    uploaded_by = TemplateColumn('''
        {% load i18n %}
        {% if record.uploaded_by %}
            {{ record.uploaded_by }}
        {% else %}
            <em>{% trans "anonymous user" %}</em>
        {% endif %}''')
    deserializaled = TemplateColumn('{{ record.is_deserialized|yesno }}')

    def get_queryset(self, bundle_stream):
        return bundle_stream.bundles.select_related(
            'bundle_stream', 'deserialization_error')

    datatable_opts = {
        'aaSorting': [[4, 'desc']],
        'sPaginationType': 'full_numbers',
        'iDisplayLength': 25,
#        'aLengthMenu': [[10, 25, 50, -1], [10, 25, 50, "All"]],
        'sDom': 'lfr<"#master-toolbar">t<"F"ip>',
        }

    searchable_columns = ['content_filename']


def bundle_list_table_json(request, pathname):
    bundle_stream = get_restricted_object_or_404(
        BundleStream,
        lambda bundle_stream: bundle_stream,
        request.user,
        pathname=pathname
    )
    return BundleTable.json(request, params=(bundle_stream,))


@BreadCrumb(
    "Bundles in {pathname}",
    parent=bundle_stream_list,
    needs=['pathname'])
def bundle_list(request, pathname):
    """
    List of bundles in a specified bundle stream.
    """
    bundle_stream = get_restricted_object_or_404(
        BundleStream,
        lambda bundle_stream: bundle_stream,
        request.user,
        pathname=pathname
    )
    return render_to_response(
        "dashboard_app/bundle_list.html",
        {
            'bundle_table': BundleTable(
                'bundle-table',
                reverse(
                    bundle_list_table_json, kwargs=dict(pathname=pathname)),
                params=(bundle_stream,)),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                bundle_list,
                pathname=pathname),
            "bundle_stream": bundle_stream
            },
        RequestContext(request))


@BreadCrumb(
    "Bundle {content_sha1}",
    parent=bundle_list,
    needs=['pathname', 'content_sha1'])
def bundle_detail(request, pathname, content_sha1):
    """
    Detail about a bundle from a particular stream
    """
    bundle_stream = get_restricted_object_or_404(
        BundleStream,
        lambda bundle_stream: bundle_stream,
        request.user,
        pathname=pathname
    )
    return object_detail(
        request,
        queryset=bundle_stream.bundles.all(),
        slug=content_sha1,
        slug_field="content_sha1",
        template_name="dashboard_app/bundle_detail.html",
        template_object_name="bundle",
        extra_context={
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                bundle_detail,
                pathname=pathname,
                content_sha1=content_sha1),
            "site": Site.objects.get_current(),
            "bundle_stream": bundle_stream
        })


def bundle_json(request, pathname, content_sha1):
    bundle_stream = get_restricted_object_or_404(
        BundleStream,
        lambda bundle_stream: bundle_stream,
        request.user,
        pathname=pathname
    )
    bundle = bundle_stream.bundles.get(content_sha1=content_sha1)
    test_runs = []
    for test_run in bundle.test_runs.all():
        results = test_run.get_summary_results()

        measurements = [{'item': str(item.test_case),
                           'measurement': str(item.measurement),
                           'units': str(item.units)
                          }
                for item in test_run.test_results.filter(
                            measurement__isnull=False).
                        order_by('test_case__test_case_id')]
        results['measurements'] = measurements

        test_runs.append({
            'name': test_run.test.test_id,
            'url': request.build_absolute_uri(test_run.get_absolute_url()),
            'results': results
            })
    json_text = json.dumps({
        'test_runs':test_runs,
        })
    content_type = 'application/json'
    if 'callback' in request.GET:
        json_text = '%s(%s)'%(request.GET['callback'], json_text)
        content_type = 'text/javascript'
    return HttpResponse(json_text, content_type=content_type)


def ajax_bundle_viewer(request, pk):
    bundle = get_restricted_object_or_404(
        Bundle,
        lambda bundle: bundle.bundle_stream,
        request.user,
        pk=pk
    )
    return render_to_response(
        "dashboard_app/_ajax_bundle_viewer.html", {
            "bundle": bundle
        },
        RequestContext(request))


class TestRunTable(DataTablesTable):

    record = TemplateColumn(
        '<a href="{{ record.get_absolute_url }}">'
        '<code>{{ record.test }} results<code/></a>',
        accessor="test__test_id",
        )

    test = TemplateColumn(
        '<a href="{{ record.test.get_absolute_url }}">{{ record.test }}</a>',
        accessor="test__test_id",
        )

    uploaded_on = TemplateColumn(
        '{{ record.bundle.uploaded_on|date:"Y-m-d H:i:s" }}',
        accessor='bundle__uploaded_on')

    analyzed_on = TemplateColumn(
        '{{ record.analyzer_assigned_date|date:"Y-m-d H:i:s" }}',
        accessor='analyzer_assigned_date')

    def get_queryset(self, bundle_stream):
        return TestRun.objects.filter(
                bundle__bundle_stream=bundle_stream
            ).select_related(
                "test",
                "bundle",
                "bundle__bundle_stream",
                "test_results"
            ).only(
                "analyzer_assigned_uuid",  # needed by TestRun.__unicode__
                "analyzer_assigned_date",  # used by the view
                "bundle__uploaded_on",  # needed by Bundle.get_absolute_url
                "bundle__content_sha1",   # needed by Bundle.get_absolute_url
                "bundle__bundle_stream__pathname",  # Needed by TestRun.get_absolute_url
                "test__name",  # needed by Test.__unicode__
                "test__test_id",  # needed by Test.__unicode__
            )

    datatable_opts = {
        "sPaginationType": "full_numbers",
        "aaSorting": [[1, "desc"]],
        "iDisplayLength": 25,
        "sDom": 'lfr<"#master-toolbar">t<"F"ip>'
        }

    searchable_columns = ['test__test_id']


def test_run_list_json(request, pathname):
    bundle_stream = get_restricted_object_or_404(
        BundleStream,
        lambda bundle_stream: bundle_stream,
        request.user,
        pathname=pathname
    )
    return TestRunTable.json(request, params=(bundle_stream,))


@BreadCrumb(
    "Test runs in {pathname}",
    parent=bundle_stream_list,
    needs=['pathname'])
def test_run_list(request, pathname):
    """
    List of test runs in a specified bundle stream.
    """
    bundle_stream = get_restricted_object_or_404(
        BundleStream,
        lambda bundle_stream: bundle_stream,
        request.user,
        pathname=pathname
    )
    return render_to_response(
        'dashboard_app/test_run_list.html', {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                test_run_list,
                pathname=pathname),
            "test_run_table": TestRunTable(
                'test-runs',
                reverse(test_run_list_json, kwargs=dict(pathname=pathname)),
                params=(bundle_stream,)),
            "bundle_stream": bundle_stream,
        }, RequestContext(request)
    )


class TestTable(DataTablesTable):

    relative_index = Column(
        verbose_name="#", attrs=Attrs(th=dict(style="width: 1%")),
        default=mark_safe("<em>Not specified</em>"))

    test_case = Column()

    result = TemplateColumn('''
        <a href="{{record.get_absolute_url}}">
          <img src="{{ STATIC_URL }}dashboard_app/images/icon-{{ record.result_code }}.png"
          alt="{{ record.get_result_display }}" width="16" height="16" border="0"/></a>
        <a href ="{{record.get_absolute_url}}">{{ record.get_result_display }}</a>
        ''')

    units = TemplateColumn(
        '{{ record.measurement|default_if_none:"Not specified" }} {{ record.units }}',
        verbose_name="measurement")

    def get_queryset(self, test_run):
        return test_run.get_results()

    datatable_opts = {
        'sPaginationType': "full_numbers",
        }

    searchable_columns = ['test_case__test_case_id']



def test_run_detail_test_json(request, pathname, content_sha1, analyzer_assigned_uuid):
    test_run = get_restricted_object_or_404(
        TestRun, lambda test_run: test_run.bundle.bundle_stream,
        request.user,
        analyzer_assigned_uuid=analyzer_assigned_uuid
        )
    return TestTable.json(request, params=(test_run,))


@BreadCrumb(
    "Run {analyzer_assigned_uuid}",
    parent=bundle_detail,
    needs=['pathname', 'content_sha1', 'analyzer_assigned_uuid'])
def test_run_detail(request, pathname, content_sha1, analyzer_assigned_uuid):
    test_run = get_restricted_object_or_404(
        TestRun,
        lambda test_run: test_run.bundle.bundle_stream,
        request.user,
        analyzer_assigned_uuid=analyzer_assigned_uuid
    )
    return render_to_response(
        "dashboard_app/test_run_detail.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                test_run_detail,
                pathname=pathname,
                content_sha1=content_sha1,
                analyzer_assigned_uuid=analyzer_assigned_uuid),
            "test_run": test_run,
            "test_table": TestTable(
                'test-table',
                reverse(test_run_detail_test_json, kwargs=dict(
                    pathname=pathname,
                    content_sha1=content_sha1,
                    analyzer_assigned_uuid=analyzer_assigned_uuid)),
                params=(test_run,))

        }, RequestContext(request))


@BreadCrumb(
    "Software Context",
    parent=test_run_detail,
    needs=['pathname', 'content_sha1', 'analyzer_assigned_uuid'])
def test_run_software_context(request, pathname, content_sha1, analyzer_assigned_uuid):
    test_run = get_restricted_object_or_404(
        TestRun,
        lambda test_run: test_run.bundle.bundle_stream,
        request.user,
        analyzer_assigned_uuid=analyzer_assigned_uuid
    )
    return render_to_response(
        "dashboard_app/test_run_software_context.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                test_run_software_context,
                pathname=pathname,
                content_sha1=content_sha1,
                analyzer_assigned_uuid=analyzer_assigned_uuid),
            "test_run": test_run
        }, RequestContext(request))


@BreadCrumb(
    "Hardware Context",
    parent=test_run_detail,
    needs=['pathname', 'content_sha1', 'analyzer_assigned_uuid'])
def test_run_hardware_context(request, pathname, content_sha1, analyzer_assigned_uuid):
    test_run = get_restricted_object_or_404(
        TestRun,
        lambda test_run: test_run.bundle.bundle_stream,
        request.user,
        analyzer_assigned_uuid=analyzer_assigned_uuid
    )
    return render_to_response(
        "dashboard_app/test_run_hardware_context.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                test_run_hardware_context,
                pathname=pathname,
                content_sha1=content_sha1,
                analyzer_assigned_uuid=analyzer_assigned_uuid),
            "test_run": test_run
        }, RequestContext(request))


@BreadCrumb(
    "Details of result {relative_index}",
    parent=test_run_detail,
    needs=['pathname', 'content_sha1', 'analyzer_assigned_uuid', 'relative_index'])
def test_result_detail(request, pathname, content_sha1, analyzer_assigned_uuid, relative_index):
    test_run = get_restricted_object_or_404(
        TestRun,
        lambda test_run: test_run.bundle.bundle_stream,
        request.user,
        analyzer_assigned_uuid=analyzer_assigned_uuid
    )
    test_result = test_run.test_results.get(relative_index=relative_index)
    return render_to_response(
        "dashboard_app/test_result_detail.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                test_result_detail,
                pathname=pathname,
                content_sha1=content_sha1,
                analyzer_assigned_uuid=analyzer_assigned_uuid,
                relative_index=relative_index),
            "test_result": test_result
        }, RequestContext(request))


@BreadCrumb(
    "Attachments",
    parent=test_run_detail,
    needs=['pathname', 'content_sha1', 'analyzer_assigned_uuid'])
def attachment_list(request, pathname, content_sha1, analyzer_assigned_uuid):
    test_run = get_restricted_object_or_404(
        TestRun,
        lambda test_run: test_run.bundle.bundle_stream,
        request.user,
        analyzer_assigned_uuid=analyzer_assigned_uuid
    )
    return object_list(
        request,
        queryset=test_run.attachments.all(),
        template_name="dashboard_app/attachment_list.html",
        template_object_name="attachment",
        extra_context={
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                attachment_list,
                pathname=pathname,
                content_sha1=content_sha1,
                analyzer_assigned_uuid=analyzer_assigned_uuid),
            'test_run': test_run})


@BreadCrumb(
    "{content_filename}",
    parent=attachment_list,
    needs=['pathname', 'content_sha1', 'analyzer_assigned_uuid', 'pk'])
def attachment_detail(request, pathname, content_sha1, analyzer_assigned_uuid, pk):
    attachment = get_restricted_object_or_404(
        Attachment,
        lambda attachment: attachment.test_run.bundle.bundle_stream,
        request.user,
        pk = pk
    )
    return render_to_response(
        "dashboard_app/attachment_detail.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                attachment_detail,
                pathname=pathname,
                content_sha1=content_sha1,
                analyzer_assigned_uuid=analyzer_assigned_uuid,
                pk=pk,
                content_filename=attachment.content_filename),
            "attachment": attachment,
        }, RequestContext(request))


def ajax_attachment_viewer(request, pk):
    attachment = get_restricted_object_or_404(
        Attachment,
        lambda attachment: attachment.test_run.bundle.bundle_stream,
        request.user,
        pk=pk
    )
    data = attachment.get_content_if_possible(
        mirror=request.user.is_authenticated())
    if attachment.mime_type == "text/plain":
        return render_to_response(
            "dashboard_app/_ajax_attachment_viewer.html", {
                "attachment": attachment,
                "lines": data.splitlines() if data else None,
            },
            RequestContext(request))
    else:
        response = HttpResponse(mimetype=attachment.mime_type)
        response['Content-Disposition'] = 'attachment; filename=%s' % (
                                           attachment.content_filename)
        response.write(data)
        return response


@BreadCrumb("Reports", parent=index)
def report_list(request):
    return render_to_response(
        "dashboard_app/report_list.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(report_list),
            "report_list": DataReport.repository.all()
        }, RequestContext(request))


@BreadCrumb("{title}", parent=report_list, needs=['name'])
def report_detail(request, name):
    try:
        report = DataReport.repository.get(name=name)
    except DataReport.DoesNotExist:
        raise Http404('No report matches given name.')
    return render_to_response(
        "dashboard_app/report_detail.html", {
            "is_iframe": request.GET.get("iframe") == "yes",
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                report_detail,
                name=report.name,
                title=report.title),
            "report": report,
        }, RequestContext(request))


@BreadCrumb("Data views", parent=index)
def data_view_list(request):
    return render_to_response(
        "dashboard_app/data_view_list.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(data_view_list),
            "data_view_list": DataView.repository.all(),
        }, RequestContext(request))


@BreadCrumb(
    "Details of {name}",
    parent=data_view_list,
    needs=['name'])
def data_view_detail(request, name):
    try:
        data_view = DataView.repository.get(name=name)
    except DataView.DoesNotExist:
        raise Http404('No data view matches the given query.')
    return render_to_response(
        "dashboard_app/data_view_detail.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                data_view_detail,
                name=data_view.name,
                summary=data_view.summary),
            "data_view": data_view
        }, RequestContext(request))


@BreadCrumb("Tests", parent=index)
def test_list(request):
    return object_list(
        request,
        queryset=Test.objects.all(),
        template_name="dashboard_app/test_list.html",
        template_object_name="test",
        extra_context={
            'bread_crumb_trail': BreadCrumbTrail.leading_to(test_list)
        })


@BreadCrumb("Details of {test_id}", parent=test_list, needs=['test_id'])
def test_detail(request, test_id):
    return object_detail(
        request,
        queryset=Test.objects.all(),
        slug=test_id,
        slug_field="test_id",
        template_name="dashboard_app/test_detail.html",
        template_object_name="test",
        extra_context={
            'bread_crumb_trail': BreadCrumbTrail.leading_to(test_detail, test_id=test_id)
        })


def redirect_to(request, object, trailing):
    url = object.get_absolute_url() + trailing
    qs = request.META.get('QUERY_STRING')
    if qs:
        url += '?' + qs
    return redirect(url)


def redirect_to_test_run(request, analyzer_assigned_uuid, trailing=''):
    test_run = get_restricted_object_or_404(
        TestRun,
        lambda test_run: test_run.bundle.bundle_stream,
        request.user,
        analyzer_assigned_uuid=analyzer_assigned_uuid)
    return redirect_to(request, test_run, trailing)


def redirect_to_test_result(request, analyzer_assigned_uuid, relative_index,
                            trailing=''):
    test_result = get_restricted_object_or_404(
        TestResult,
        lambda test_result: test_result.test_run.bundle.bundle_stream,
        request.user,
        test_run__analyzer_assigned_uuid=analyzer_assigned_uuid,
        relative_index=relative_index)
    return redirect_to(request, test_result, trailing)


def redirect_to_bundle(request, content_sha1, trailing=''):
    bundle = get_restricted_object_or_404(
        Bundle,
        lambda bundle: bundle.bundle_stream,
        request.user,
        content_sha1=content_sha1)
    return redirect_to(request, bundle, trailing)


@BreadCrumb("Testing efforts", parent=index)
def testing_effort_list(request):
    return render_to_response(
        "dashboard_app/testing_effort_list.html", {
            'effort_list': TestingEffort.objects.all(
            ).order_by('name'),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                testing_effort_list),
        }, RequestContext(request))


@BreadCrumb(
    "{effort}",
    parent=testing_effort_list,
    needs=["pk"])
def testing_effort_detail(request, pk):
    effort = get_object_or_404(TestingEffort, pk=pk)
    return render_to_response(
        "dashboard_app/testing_effort_detail.html", {
            'effort': effort,
            'belongs_to_user': effort.project.is_owned_by(request.user),
            'test_run_list': effort.get_test_runs(
            ).select_related(
                'denormalization',
                'bundle',
                'bundle__bundle_stream',
                'test',
            ),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                testing_effort_detail,
                effort=effort,
                pk=pk),
        }, RequestContext(request))


from lava_projects.models import Project
from lava_projects.views import project_detail
from dashboard_app.forms import TestingEffortForm


@BreadCrumb(
    "Start a new test effort",
    parent=project_detail,
    needs=["project_identifier"])
@login_required
def testing_effort_create(request, project_identifier):
    project = get_object_or_404(Project, identifier=project_identifier)
    if request.method == 'POST':
        form = TestingEffortForm(request.POST)
        # Check the form
        if form.is_valid():
            # And make a project instance
            effort = TestingEffort.objects.create(
                name=form.cleaned_data['name'],
                description=form.cleaned_data['description'],
                project=project)
            # Create all the required tags
            effort.tags = [
                Tag.objects.get_or_create(name=tag_name)[0]
                for tag_name in re.split("[, ]+", form.cleaned_data["tags"])
                if tag_name != ""]
            return HttpResponseRedirect(effort.get_absolute_url())
    else:
        form = TestingEffortForm()
    # Render to template
    template_name = "dashboard_app/testing_effort_form.html"
    t = loader.get_template(template_name)
    c = RequestContext(request, {
        'form': form,
        'bread_crumb_trail': BreadCrumbTrail.leading_to(
            testing_effort_create,
            project=project,
            project_identifier=project.identifier)
    })
    return HttpResponse(t.render(c))


@BreadCrumb(
    "Update",
    parent=testing_effort_detail,
    needs=["pk"])
@login_required
def testing_effort_update(request, pk):
    try:
        effort = TestingEffort.objects.get(pk=pk)
    except TestingEffort.DoesNotExist:
        raise Http404()
    if not effort.project.is_owned_by(request.user):
        return HttpResponse("not allowed")
    if request.method == 'POST':
        form = TestingEffortForm(request.POST)
        # Check the form
        if form.is_valid():
            # And update the effort object
            effort.name=form.cleaned_data['name']
            effort.description=form.cleaned_data['description']
            # As well as tags
            effort.tags = [
                Tag.objects.get_or_create(name=tag_name)[0]
                for tag_name in re.split("[, ]+", form.cleaned_data["tags"])
                if tag_name != ""]
            # Save the changes
            effort.save()
            return HttpResponseRedirect(effort.get_absolute_url())
    else:
        form = TestingEffortForm(initial={
            'name': effort.name,
            'description': effort.description,
            'tags': " ".join([tag.name for tag in effort.tags.order_by('name').all()])
        })
    # Render to template
    template_name = "dashboard_app/testing_effort_form.html"
    t = loader.get_template(template_name)
    c = RequestContext(request, {
        'form': form,
        'effort': effort,
        'bread_crumb_trail': BreadCrumbTrail.leading_to(
            testing_effort_update,
            effort=effort,
            pk=effort.pk)
    })
    return HttpResponse(t.render(c))
