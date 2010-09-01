"""
Views for the Dashboard application
"""

# Original inspiration from:
# Brendan W. McAdams <brendan.mcadams@thewintergrp.com>
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render_to_response

from launch_control.dashboard_app.dispatcher import DjangoXMLRPCDispatcher
from launch_control.dashboard_app.models import DashboardAPI


def _get_dashboard_dispatcher():
    """
    Build dashboard XML-RPC dispatcher.
    """
    dispatcher = DjangoXMLRPCDispatcher()
    dispatcher.register_instance(DashboardAPI())
    dispatcher.register_introspection_functions()
    return dispatcher


DashboardDispatcher = _get_dashboard_dispatcher()


def xml_rpc_handler(request, dispatcher):
    """
    XML-RPC handler.

    If post data is defined, it assumes it's XML-RPC and tries to
    process as such Empty post assumes you're viewing from a browser and
    tells you about the service.
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
