# Copyright (C) 2010 Linaro Limited
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

from django.contrib.auth.decorators import login_required
from django.contrib.csrf.middleware import csrf_exempt
from django.contrib.sites.models import Site
from django.db.models.manager import Manager
from django.db.models.query import QuerySet
from django.http import (HttpResponse, Http404)
from django.shortcuts import render_to_response
from django.template import RequestContext

from dashboard_app.dispatcher import DjangoXMLRPCDispatcher
from dashboard_app.models import (Attachment, Bundle, BundleStream, TestRun, TestResult)
from dashboard_app.xmlrpc import DashboardAPI


def _get_dashboard_dispatcher():
    """
    Build dashboard XML-RPC dispatcher.
    """
    dispatcher = DjangoXMLRPCDispatcher()
    dispatcher.register_instance(DashboardAPI())
    dispatcher.register_introspection_functions()
    return dispatcher


DashboardDispatcher = _get_dashboard_dispatcher()


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


# Original inspiration from:
# Brendan W. McAdams <brendan.mcadams@thewintergrp.com>
def xml_rpc_handler(request, dispatcher):
    """
    XML-RPC handler.

    If post data is defined, it assumes it's XML-RPC and tries to
    process as such. Empty POST request and GET requests assumes you're
    viewing from a browser and tells you about the service.
    """
    if len(request.POST):
        raw_data = request.raw_post_data
        response = HttpResponse(mimetype="application/xml")
        result = dispatcher._marshaled_dispatch(raw_data)
        response.write(result)
        response['Content-length'] = str(len(response.content))
        return response
    else:
        methods = [{
            'name': method,
            'signature': dispatcher.system_methodSignature(method),
            'help': dispatcher.system_methodHelp(method)}
            for method in dispatcher.system_listMethods()]
        return render_to_response(
            'dashboard_app/api.html', {
                'methods': methods,
                'dashboard_url': "http://{domain}".format(
                    domain = Site.objects.get_current().domain)
            }, RequestContext(request)
        )


@csrf_exempt
def dashboard_xml_rpc_handler(request):
    return xml_rpc_handler(request, DashboardDispatcher)


def bundle_stream_list(request):
    """
    List of bundle streams.

    The list is paginated and dynamically depends on the currently
    logged in user.
    """
    return render_to_response(
        'dashboard_app/bundle_stream_list.html', {
            "bundle_stream_list": BundleStream.objects.accessible_by_principal(request.user).order_by('pathname'),
            'has_personal_streams': (
                request.user.is_authenticated() and
                BundleStream.objects.filter(user=request.user).count() > 0),
            'has_team_streams': (
                request.user.is_authenticated() and
                BundleStream.objects.filter(
                    group__in = request.user.groups.all()).count() > 0),
        }, RequestContext(request)
    )


def test_run_list(request, pathname):
    """
    List of test runs in a specified bundle stream.

    The list is paginated and dynamically depends on the currently
    logged in user.
    """
    bundle_stream = get_restricted_object_or_404(
        BundleStream,
        lambda bundle_stream: bundle_stream,
        request.user,
        pathname=pathname
    )
    return render_to_response(
        'dashboard_app/test_run_list.html', {
            "test_run_list": TestRun.objects.filter(bundle__bundle_stream=bundle_stream).order_by('-bundle__uploaded_on'),
            "bundle_stream": bundle_stream,
        }, RequestContext(request)
    )


def bundle_list(request, pathname):
    """
    List of bundles in a specified bundle stream.

    The list is paginated and dynamically depends on the currently logged in
    user.
    """
    bundle_stream = get_restricted_object_or_404(
        BundleStream,
        lambda bundle_stream: bundle_stream,
        request.user,
        pathname=pathname
    )
    return render_to_response(
        'dashboard_app/bundle_list.html', {
            "bundle_list": bundle_stream.bundles.all().order_by('-uploaded_on'),
            "bundle_stream": bundle_stream,
        }, RequestContext(request)
    )


def _test_run_view(template_name):
    def view(request, analyzer_assigned_uuid):
        test_run = get_restricted_object_or_404(
            TestRun,
            lambda test_run: test_run.bundle.bundle_stream,
            request.user,
            analyzer_assigned_uuid = analyzer_assigned_uuid
        )
        return render_to_response(
            template_name, {
                "test_run": test_run
            }, RequestContext(request)
        )
    return view


test_run_detail = _test_run_view("dashboard_app/test_run_detail.html")
test_run_software_context = _test_run_view("dashboard_app/test_run_software_context.html")
test_run_hardware_context = _test_run_view("dashboard_app/test_run_hardware_context.html")


def test_result_detail(request, pk):
    test_result = get_restricted_object_or_404(
        TestResult,
        lambda test_result: test_result.test_run.bundle.bundle_stream,
        request.user,
        pk = pk
    )
    return render_to_response(
        "dashboard_app/test_result_detail.html", {
            "test_result": test_result
        }, RequestContext(request)
    )


def auth_test(request):
    response = HttpResponse(mimetype="text/plain")
    if (request.user and request.user.is_authenticated and
        request.user.is_active):
        response.write(request.user.username)
    response['Content-length'] = str(len(response.content))
    return response


@login_required
def restricted_view(request):
    return HttpResponse("Well you are here")


def attachment_detail(request, pk):
    attachment = get_restricted_object_or_404(
        Attachment,
        lambda attachment: attachment.content_object.bundle.bundle_stream,
        request.user,
        pk = pk
    )
    if attachment.mime_type == "text/plain":
        data = attachment.get_content_if_possible(mirror=request.user.is_authenticated())
    else:
        data = None
    return render_to_response(
        "dashboard_app/attachment_detail.html", {
            "lines": data.splitlines() if data else None,
            "attachment": attachment,
        }, RequestContext(request)
    )
