#!/usr/bin/python
from lava.actions import BaseAction
from lava.config import LAVA_RESULT_DIR
import xmlrpclib
import sys
import socket

class cmd_submit_results(BaseAction):
    def run(self, server, stream, pathname):
        dashboard_url = "%s/launch-control" % server
        xmlrpc_url = "%s/launch-control/xml-rpc/" % server
        filename = "%s/%s.bundle" % (LAVA_RESULT_DIR, stream)

        srv = xmlrpclib.ServerProxy(xmlrpc_url, 
                allow_none=True, use_datetime=True)
        f = open("%s" % filename, "rb")
        content = f.read()
        f.close()

        content_sha1 = srv.put(content, filename, pathname)
        return content_sha1
