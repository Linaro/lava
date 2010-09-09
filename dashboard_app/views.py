"""
Views for the Dashboard application
"""

from django.http import HttpResponse
from django.shortcuts import (
        get_object_or_404,
        render_to_response,
        )
from django.views.generic import list_detail

from dashboard_app.dispatcher import DjangoXMLRPCDispatcher
from dashboard_app.models import (Bundle, BundleStream)
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
        return render_to_response('dashboard_app/api.html',
                {'methods': methods})


def dashboard_xml_rpc_handler(request):
    return xml_rpc_handler(request, DashboardDispatcher)


def bundle_stream_list(request):
    """
    List of bundle streams.

    The list is paginated and dynamically depends on the currently
    logged in user.
    """
    bundle_streams = BundleStream.get_allowed_for_user(request.user).order_by('pathname')
    return list_detail.object_list(request,
            paginate_by = 25,
            queryset = bundle_streams,
            template_name = 'dashboard_app/bundle_stream_list.html',
            template_object_name = 'bundle_stream',
            )


def bundle_stream_detail(request, pathname):
    """
    List of bundle streams.

    The list is paginated and dynamically depends on the currently
    logged in user.
    """
    bundle_stream = get_object_or_404(BundleStream, pathname=pathname)
    if bundle_stream.can_access(request.user):
        return list_detail.object_detail(request,
                queryset = BundleStream.objects.all(),
                slug_field = 'pathname',
                slug = pathname,
                template_name = 'dashboard_app/bundle_stream_detail.html',
                template_object_name = 'bundle_stream',
                )
    else:
        resp = render_to_response("403.html",
                context_instance=RequestContext(request))
        resp.status_code = 403
        return resp
