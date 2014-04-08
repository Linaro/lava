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

import csv
import json
import os
import re
import shutil
import tempfile

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core import serializers
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.db.models.manager import Manager
from django.db.models.query import QuerySet
from django.db.models import Count, Q
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
)
from django.shortcuts import render_to_response, redirect, get_object_or_404
from django.template import RequestContext, loader
from django.utils.safestring import mark_safe
from django.forms import ModelForm
from lava_server.views import index as lava_index
from lava_server.bread_crumbs import (
    BreadCrumb,
    BreadCrumbTrail,
)
from dashboard_app.models import (
    Attachment,
    Bundle,
    BundleStream,
    Tag,
    Test,
    TestCase,
    TestResult,
    TestRun,
    TestDefinition,
)
from lava_scheduler_app.models import (
    TestJob
)
from dashboard_app.views.tables import (
    BundleStreamTable,
    BundleTable,
    BundleDetailTable,
    TestRunTable,
    TestTable,
    TestDefinitionTable,
)
from django_tables2 import (
    Attrs,
    Column,
    RequestConfig,
    SingleTableView,
    TemplateColumn,
)
from lava.utils.lavatable import LavaView


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


def get_restricted_object(klass, via, user, *args, **kwargs):
    """
    Uses get() to return an object, or raises a Http404 exception if the object
    does not exist. If the object exists access control check is made
    using the via callback (via is called with the found object and the return
    value must be a RestrictedResource subclass. If the user doesn't have
    permission to view the resource a 403 error will be displayed.

    klass may be a Model, Manager, or QuerySet object. All other passed
    arguments and keyword arguments are used in the get() query.

    Note: Like with get(), an MultipleObjectsReturned will be raised if more
    than one object is found.
    """
    queryset = _get_queryset(klass)
    try:
        obj = queryset.get(*args, **kwargs)
        ownership_holder = via(obj)
        if not user.is_superuser:
            if not ownership_holder.is_accessible_by(user):
                raise PermissionDenied()
        return obj
    except queryset.model.DoesNotExist:
        raise Http404('No %s matches the given query.' % queryset.model._meta.object_name)


class BundleStreamView(LavaView):

    def get_queryset(self):
        if self.request.user.is_superuser:
            return BundleStream.objects.all().order_by('pathname')
        else:
            return BundleStream.objects.accessible_by_principal(
                self.request.user).order_by('pathname')

    def results_query(self, term):
        matches = [p for p, r in TestResult.RESULT_MAP.iteritems() if r == term]
        return Q(result__in=matches)

    def test_case_query(self, term):
        test_cases = TestCase.objects.filter(test_case_id__contains=term)
        return Q(test_case__in=test_cases)

    def test_run_query(self, term):
        test_runs = Test.objects.filter(test_id__contains=term)
        return Q(test_id__in=test_runs)


class MyBundleStreamView(BundleStreamView):

    def get_queryset(self):
        return BundleStream.objects.owned_by_principal(self.request.user).order_by('pathname')


@BreadCrumb("Dashboard", parent=lava_index)
def index(request):
    return render_to_response(
        "dashboard_app/index.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(index)
        }, RequestContext(request))


@BreadCrumb("My Bundle Streams", parent=index)
def mybundlestreams(request):
    data = MyBundleStreamView(request, model=BundleStream, table_class=BundleStreamTable)
    table = BundleStreamTable(data.get_table_data())
    RequestConfig(request, paginate={"per_page": table.length}).configure(table)
    return render_to_response(
        "dashboard_app/mybundlestreams.html",
        {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(mybundlestreams),
            "bundle_stream_table": table,
            "terms_data": table.prepare_terms_data(data),
            "search_data": table.prepare_search_data(data),
            "discrete_data": table.prepare_discrete_data(data),
        },
        RequestContext(request))


@BreadCrumb("Bundle Streams", parent=index)
def bundle_stream_list(request):
    """
    List of bundle streams.
    """
    data = BundleStreamView(request, model=BundleStream, table_class=BundleStreamTable)
    table = BundleStreamTable(data.get_table_data())
    RequestConfig(request, paginate={"per_page": table.length}).configure(table)
    return render_to_response(
        'dashboard_app/bundle_stream_list.html', {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                bundle_stream_list),
            "bundle_stream_table": table,
            "terms_data": table.prepare_terms_data(data),
            "search_data": table.prepare_search_data(data),
            "discrete_data": table.prepare_discrete_data(data),
            'has_personal_streams': (
                request.user.is_authenticated() and
                BundleStream.objects.filter(user=request.user).count() > 0),
            'has_team_streams': (
                request.user.is_authenticated() and
                BundleStream.objects.filter(
                    group__in=request.user.groups.all()).count() > 0),
        }, RequestContext(request)
    )


class BundleView(BundleStreamView):

    def __init__(self, request, bundle_stream, **kwargs):
        super(BundleView, self).__init__(request, **kwargs)
        self.bundle_stream = bundle_stream

    def get_queryset(self):
        return self.bundle_stream.bundles.select_related(
            'bundle_stream', 'deserialization_error').order_by('-uploaded_on')


@BreadCrumb(
    "Bundles in {pathname}",
    parent=bundle_stream_list,
    needs=['pathname'])
def bundle_list(request, pathname):
    """
    List of bundles in a specified bundle stream.
    """
    bundle_stream = get_restricted_object(
        BundleStream,
        lambda bundle_stream: bundle_stream,
        request.user,
        pathname=pathname
    )
    data = BundleView(request, bundle_stream, model=Bundle, table_class=BundleTable)
    table = BundleTable(data.get_table_data())
    RequestConfig(request, paginate={"per_page": table.length}).configure(table)
    return render_to_response(
        "dashboard_app/bundle_list.html",
        {
            'bundle_list': table,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                bundle_list,
                pathname=pathname),
            "terms_data": table.prepare_terms_data(data),
            "search_data": table.prepare_search_data(data),
            "discrete_data": table.prepare_discrete_data(data),
            "times_data": table.prepare_times_data(data),
            "bundle_stream": bundle_stream,
        },
        RequestContext(request))


def _remove_dir(path):
    """ Removes directory @path. Doesn't raise exceptions. """
    try:
        # Delete directory.
        shutil.rmtree(path)
    except OSError as exception:
        # Silent exception whatever happens. If it's unexisting dir, we don't
        # care.
        pass


def bundle_list_export(request, pathname):
    """
    Create and serve the CSV file.
    """
    bundle_stream = get_restricted_object(
        BundleStream,
        lambda bundle_stream: bundle_stream,
        request.user,
        pathname=pathname
    )

    file_name = bundle_stream.slug
    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, "%s.csv" % file_name)

    bundle_keys = []
    for bundle in bundle_stream.bundles.all():
        bundle_keys = bundle.__dict__.keys()
        break

    bundle_keys.sort()
    # Remove non-relevant columns for CSV file.
    removed_fields = ["_gz_content", "_raw_content", "_state", "id",
                      "bundle_stream_id"]
    for field in removed_fields:
        if field in bundle_keys:
            bundle_keys.remove(field)

    # Add results columns from denormalization object.
    bundle_keys.extend(["pass", "fail", "total"])

    with open(file_path, 'w+') as csv_file:
        out = csv.DictWriter(csv_file, quoting=csv.QUOTE_ALL,
                             extrasaction='ignore',
                             fieldnames=bundle_keys)
        out.writeheader()

        for bundle in bundle_stream.bundles.all():
            # Add results columns from summary results.
            bundle_dict = bundle.__dict__.copy()
            summary_results = bundle.get_summary_results()
            if summary_results:
                bundle_dict.update(summary_results)
            else:
                bundle_dict["pass"] = 0
                bundle_dict["fail"] = 0
                bundle_dict["total"] = 0
            bundle_dict["uploaded_by_id"] = User.objects.get(
                pk=bundle.uploaded_by_id).username
            out.writerow(bundle_dict)

    response = HttpResponse(mimetype='text/csv')
    response['Content-Disposition'] = "attachment; filename=%s.csv" % file_name
    with open(file_path, 'r') as csv_file:
        response.write(csv_file.read())

    _remove_dir(tmp_dir)
    return response


class BundleDetailView(BundleStreamView):
    """
    View of a bundle from a particular stream
    """

    def __init__(self, request, pathname, content_sha1, **kwargs):
        super(BundleDetailView, self).__init__(request, **kwargs)
        self.pathname = pathname
        self.content_sha1 = content_sha1

    def get_queryset(self):
        bundle_stream = BundleStream.objects.filter(pathname=self.pathname)
        if not bundle_stream[0].is_accessible_by(self.request.user):
            raise PermissionDenied
        bundle = Bundle.objects.filter(bundle_stream=bundle_stream, content_sha1=self.content_sha1)[:1][0]
        return bundle.test_runs.all().order_by('test')


@BreadCrumb(
    "Bundle {content_sha1}",
    parent=bundle_list,
    needs=['pathname', 'content_sha1'])
def bundle_detail(request, pathname, content_sha1):
    """
    Detail about a bundle from a particular stream
    """
    bundle_stream = BundleStream.objects.filter(pathname=pathname)
    bundle = Bundle.objects.filter(bundle_stream=bundle_stream, content_sha1=content_sha1)
    view = BundleDetailView(request, pathname=pathname, content_sha1=content_sha1, model=TestRun, table_class=BundleDetailTable)
    bundle_table = BundleDetailTable(view.get_table_data())
    RequestConfig(request, paginate={"per_page": bundle_table.length}).configure(bundle_table)
    return render_to_response(
        "dashboard_app/bundle_detail.html",
        {
            'bundle_table': bundle_table,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                bundle_detail,
                pathname=pathname,
                content_sha1=content_sha1),
            "terms_data": bundle_table.prepare_terms_data(view),
            "search_data": bundle_table.prepare_search_data(view),
            "discrete_data": bundle_table.prepare_discrete_data(view),
            "times_data": bundle_table.prepare_times_data(view),
            "site": Site.objects.get_current(),
            "bundle": bundle[0],
            "bundle_stream": bundle_stream[0],
        },
        RequestContext(request))


def bundle_export(request, pathname, content_sha1):
    """ Create and serve the CSV file. """

    bundle = get_restricted_object(
        Bundle,
        lambda bundle: bundle.bundle_stream,
        request.user,
        content_sha1=content_sha1)

    file_name = bundle.content_sha1
    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, "%s.csv" % file_name)

    test_run_keys = []
    for test_run in bundle.test_runs.all():
        test_run_keys = test_run.__dict__.keys()
        break

    test_run_keys.sort()
    # Remove non-relevant columns for CSV file.
    removed_fields = ["_state", "id", "bundle_id",
                      "sw_image_desc", "test_id"]
    for field in removed_fields:
        if field in test_run_keys:
            test_run_keys.remove(field)

    # Add results columns from denormalization object.
    test_run_keys[:0] = ["device", "test", "count_pass", "count_fail",
                         "count_skip", "count_unknown"]

    with open(file_path, 'w+') as csv_file:
        out = csv.DictWriter(csv_file, quoting=csv.QUOTE_ALL,
                             extrasaction='ignore',
                             fieldnames=test_run_keys)
        out.writeheader()

        for test_run in bundle.test_runs.all():
            # Add results columns from denormalization object.
            test_run_denorm = test_run.denormalization
            test_run_dict = test_run.__dict__.copy()
            test_run_dict.update(test_run_denorm.__dict__)
            test_run_dict["test"] = test_run.test.test_id
            test_run_dict["device"] = test_run.show_device()
            out.writerow(test_run_dict)

    response = HttpResponse(mimetype='text/csv')
    response['Content-Disposition'] = "attachment; filename=%s.csv" % file_name
    with open(file_path, 'r') as csv_file:
        response.write(csv_file.read())

    _remove_dir(tmp_dir)
    return response


def bundle_json(request, pathname, content_sha1):
    bundle_stream = get_restricted_object(
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
        'test_runs': test_runs,
    })
    content_type = 'application/json'
    if 'callback' in request.GET:
        json_text = '%s(%s)' % (request.GET['callback'], json_text)
        content_type = 'text/javascript'
    return HttpResponse(json_text, content_type=content_type)


def ajax_bundle_viewer(request, pk):
    bundle = get_restricted_object(
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


class TestRunView(BundleStreamView):
    """
    View of test runs in a specified bundle stream.
    """
    def __init__(self, request, bundle_stream, **kwargs):
        super(TestRunView, self).__init__(request, **kwargs)
        self.bundle_stream = bundle_stream

    def get_queryset(self):
        return TestRun.objects.filter(
            bundle__bundle_stream=self.bundle_stream
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
        ).order_by('test')


@BreadCrumb(
    "Test runs in {pathname}",
    parent=bundle_stream_list,
    needs=['pathname'])
def test_run_list(request, pathname):
    """
    List of test runs in a specified bundle in a bundle stream.
    """
    bundle_stream = get_restricted_object(
        BundleStream,
        lambda bundle_stream: bundle_stream,
        request.user,
        pathname=pathname
    )
    view = TestRunView(request, bundle_stream, model=TestRun, table_class=TestRunTable)
    table = TestRunTable(view.get_table_data())
    RequestConfig(request, paginate={"per_page": table.length}).configure(table)
    return render_to_response(
        'dashboard_app/test_run_list.html', {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                test_run_list,
                pathname=pathname),
            "test_run_table": table,
            "bundle_stream": bundle_stream,
            "terms_data": table.prepare_terms_data(view),
            "search_data": table.prepare_search_data(view),
            "discrete_data": table.prepare_discrete_data(view),
            "times_data": table.prepare_times_data(view),
        }, RequestContext(request)
    )


class TestRunDetailView(BundleStreamView):

    def __init__(self, request, test_run, analyzer_assigned_uuid, **kwargs):
        super(TestRunDetailView, self).__init__(request, **kwargs)
        self.test_run = test_run
        self.analyzer_assigned_uuid = analyzer_assigned_uuid

    def get_queryset(self):
        return self.test_run.get_results().annotate(Count("attachments"))


@BreadCrumb(
    "Run {analyzer_assigned_uuid}",
    parent=bundle_detail,
    needs=['pathname', 'content_sha1', 'analyzer_assigned_uuid'])
def test_run_detail(request, pathname, content_sha1, analyzer_assigned_uuid):
    job_list = []
    view = TestRunDetailView(request, get_restricted_object(
        TestRun,
        lambda test_run: test_run.bundle.bundle_stream,
        request.user,
        analyzer_assigned_uuid=analyzer_assigned_uuid
    ), analyzer_assigned_uuid, model=TestResult, table_class=TestTable)
    table = TestTable(view.get_table_data())
    RequestConfig(request, paginate={"per_page": table.length}).configure(table)
    return render_to_response(
        "dashboard_app/test_run_detail.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                test_run_detail,
                pathname=pathname,
                content_sha1=content_sha1,
                analyzer_assigned_uuid=analyzer_assigned_uuid),
            "test_run": view.test_run,
            "bundle": view.test_run.bundle,
            "job_list": job_list,
            "terms_data": table.prepare_terms_data(view),
            "search_data": table.prepare_search_data(view),
            "discrete_data": table.prepare_discrete_data(view),
            "times_data": table.prepare_times_data(view),
            "test_table": table,
        }, RequestContext(request))


def test_run_export(request, pathname, content_sha1, analyzer_assigned_uuid):
    """ Create and serve the CSV data file."""

    test_run = get_restricted_object(
        TestRun,
        lambda test_run: test_run.bundle.bundle_stream,
        request.user,
        analyzer_assigned_uuid=analyzer_assigned_uuid
    )

    file_name = test_run.test.test_id
    tmp_dir = tempfile.mkdtemp()
    file_path = os.path.join(tmp_dir, "%s.csv" % file_name)

    test_results = test_run.get_results()

    test_result_keys = []
    for test_result in test_results:
        test_result_keys = test_result.__dict__.keys()
        break

    test_result_keys.sort()
    # Remove non-relevant columns for CSV file.
    removed_fields = ["_state", "_order", "id", "test_run_id", "test_case_id"]
    for field in removed_fields:
        if field in test_result_keys:
            test_result_keys.remove(field)

    with open(file_path, 'w+') as csv_file:
        out = csv.DictWriter(csv_file, quoting=csv.QUOTE_ALL,
                             extrasaction='ignore',
                             fieldnames=test_result_keys)
        out.writeheader()
        for test_result in test_results:
            test_result_dict = test_result.__dict__.copy()
            # Update result field to show human readable value.
            test_result_dict["result"] = TestResult.RESULT_MAP[
                test_result_dict["result"]]
            out.writerow(test_result_dict)

    response = HttpResponse(mimetype='text/csv')
    response['Content-Disposition'] = "attachment; filename=%s.csv" % file_name
    with open(file_path, 'r') as csv_file:
        response.write(csv_file.read())

    _remove_dir(tmp_dir)
    return response


@BreadCrumb(
    "Software Context",
    parent=test_run_detail,
    needs=['pathname', 'content_sha1', 'analyzer_assigned_uuid'])
def test_run_software_context(request, pathname, content_sha1, analyzer_assigned_uuid):
    test_run = get_restricted_object(
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
    test_run = get_restricted_object(
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
    test_run = get_restricted_object(
        TestRun,
        lambda test_run: test_run.bundle.bundle_stream,
        request.user,
        analyzer_assigned_uuid=analyzer_assigned_uuid
    )
    test_result = test_run.test_results.select_related('fig').get(relative_index=relative_index)
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


@login_required
def test_result_update_comments(request, pathname, content_sha1,
                                analyzer_assigned_uuid, relative_index):

    if request.method != 'POST':
        raise PermissionDenied

    test_run = get_restricted_object(
        TestRun,
        lambda test_run: test_run.bundle.bundle_stream,
        request.user,
        analyzer_assigned_uuid=analyzer_assigned_uuid
    )
    test_result = test_run.test_results.select_related('fig').get(
        relative_index=relative_index)
    test_result.comments = request.POST.get('comments')
    test_result.save()
    data = serializers.serialize('json', [test_result])
    return HttpResponse(data, mimetype='application/json')


def attachment_download(request, pk):
    attachment = get_restricted_object(
        Attachment,
        lambda attachment: attachment.bundle.bundle_stream,
        request.user,
        pk=pk
    )
    if not attachment.content:
        return HttpResponseBadRequest(
            "Attachment %s not present on dashboard" % pk)
    response = HttpResponse(mimetype=attachment.mime_type)
    response['Content-Disposition'] = 'attachment; filename=%s' % (
        attachment.content_filename)
    response.write(attachment.content.read())
    return response


def attachment_view(request, pk):
    attachment = get_restricted_object(
        Attachment,
        lambda attachment: attachment.bundle.bundle_stream,
        request.user,
        pk=pk
    )
    if not attachment.content or not attachment.is_viewable():
        return HttpResponseBadRequest("Attachment %s not viewable" % pk)
    return render_to_response(
        "dashboard_app/attachment_view.html", {
            'attachment': attachment,
        }, RequestContext(request))


def redirect_to(request, object, trailing):
    url = object.get_absolute_url() + trailing
    qs = request.META.get('QUERY_STRING')
    if qs:
        url += '?' + qs
    return redirect(url)


def redirect_to_test_run(request, analyzer_assigned_uuid, trailing=''):
    test_run = get_restricted_object(
        TestRun,
        lambda test_run: test_run.bundle.bundle_stream,
        request.user,
        analyzer_assigned_uuid=analyzer_assigned_uuid)
    return redirect_to(request, test_run, trailing)


def redirect_to_test_result(request, analyzer_assigned_uuid, relative_index,
                            trailing=''):
    test_result = get_restricted_object(
        TestResult,
        lambda test_result: test_result.test_run.bundle.bundle_stream,
        request.user,
        test_run__analyzer_assigned_uuid=analyzer_assigned_uuid,
        relative_index=relative_index)
    return redirect_to(request, test_result, trailing)


def redirect_to_bundle(request, content_sha1, trailing=''):
    bundle = get_restricted_object(
        Bundle,
        lambda bundle: bundle.bundle_stream,
        request.user,
        content_sha1=content_sha1)
    return redirect_to(request, bundle, trailing)
