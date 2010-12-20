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
from django.contrib.sites.models import Site
from django.http import HttpResponse
from django.shortcuts import (
        get_object_or_404,
        render_to_response,
        )
from django.views.generic import list_detail
from django.template import RequestContext

from dashboard_app.dispatcher import DjangoXMLRPCDispatcher
from dashboard_app.models import (Bundle, BundleStream, TestRun)
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
        return render_to_response('dashboard_app/api.html', {
            'methods': methods,
            'dashboard_url': "http://{domain}".format(
                domain = Site.objects.get_current().domain)
        }, RequestContext(request))

from django.contrib.csrf.middleware import csrf_exempt

@csrf_exempt
def dashboard_xml_rpc_handler(request):
    return xml_rpc_handler(request, DashboardDispatcher)


def bundle_stream_list(request):
    """
    List of bundle streams.

    The list is paginated and dynamically depends on the currently
    logged in user.
    """
    bundle_streams = BundleStream.objects.allowed_for_user(request.user).order_by('pathname')
    return list_detail.object_list(
        request,
        paginate_by = 25,
        queryset = bundle_streams,
        template_name = 'dashboard_app/bundle_stream_list.html',
        template_object_name = 'bundle_stream',
        extra_context = {
            'has_personal_streams': (
                request.user.is_authenticated() and
                BundleStream.objects.filter(user=request.user).count() > 0),
            'has_team_streams': (
                request.user.is_authenticated() and
                BundleStream.objects.filter(
                    group__in = request.user.groups.all()).count() > 0),
        })


def bundle_stream_detail(request, pathname):
    """
    List of bundle streams.

    The list is paginated and dynamically depends on the currently
    logged in user.
    """
    bundle_stream = get_object_or_404(BundleStream, pathname=pathname)
    if bundle_stream.can_access(request.user):
        return list_detail.object_detail(
            request,
            queryset = BundleStream.objects.all(),
            slug_field = 'pathname',
            slug = pathname,
            template_name = 'dashboard_app/bundle_stream_detail.html',
            template_object_name = 'bundle_stream',
            extra_context = {
                'dashboard_url': "http://{domain}".format(
                    domain = Site.objects.get_current().domain)
            }
        )
    else:
        resp = render_to_response("403.html", RequestContext(request))
        resp.status_code = 403
        return resp


def test_run_detail(request, analyzer_assigned_uuid):
    test_run = get_object_or_404(TestRun, 
                                 analyzer_assigned_uuid=analyzer_assigned_uuid)
    if test_run.bundle.bundle_stream.can_access(request.user):
        from django.core.paginator import Paginator, InvalidPage, EmptyPage
        paginator = Paginator(test_run.test_results.all(), 25)
        for page in range(1, paginator.num_pages):
            # Request a page and make sure value returned is an int. 
            # If not, deliver first page.
            try: 
                page = request.GET.get('page', page)
            except ValueError:
                page = 1
            # If page request is out of range, deliver last page of results.
            try:
                test_results = paginator.page(page)
            except (EmptyPage, InvalidPage):
                test_results = paginator.page(paginator.num_pages)

            print "DEBUG ", dir(test_results)
            print "DEBUG ", test_results.start_index
#            print "DEBUG ", dir(page)
            return list_detail.object_detail(
                   request,
                   queryset = TestRun.objects.all(),
                   slug_field = 'analyzer_assigned_uuid',
                   slug = analyzer_assigned_uuid,
                   template_name = 'dashboard_app/test_run_detail.html',
                   template_object_name = 'test_run',
                   extra_context =  { 'test_results' : test_results , 
                                      'start_page' : 1 ,
                                      'end_page'   : paginator.num_pages
                                      }
                   )
    else:
        resp = render_to_response("403.html", RequestContext(request))
        resp.status_code = 403
        return resp


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
