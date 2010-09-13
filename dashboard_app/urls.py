"""
URL mappings for the Dashboard application
"""
from django.conf.urls.defaults import *

from dashboard_app.views import (
        bundle_stream_detail,
        bundle_stream_list,
        dashboard_xml_rpc_handler,
        )

urlpatterns = patterns('',
        url(r'^streams/$', bundle_stream_list,
            name='dashboard_app.bundle_stream_list'),
        url(r'^streams(?P<pathname>/[a-zA-Z0-9/-]+/)$', bundle_stream_detail,
            name='dashboard_app.bundle_stream_detail'),
        url(r'^xml-rpc/', dashboard_xml_rpc_handler,
            name='dashboard_app.dashboard_xml_rpc_handler'),
        )
