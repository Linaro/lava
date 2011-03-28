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

        try:
            content_sha1 = srv.put(content, filename, pathname)
            return content_sha1
        except socket.error as ex:
            print >> sys.stderr, "Unable to connect to server at %s" % (
                    dashboard_url,)
            # It seems that some errors are reported as -errno
            # while others as +errno.
            ex.errno = abs(ex.errno)
            if ex.errno == errno.ECONNREFUSED:
                print >> sys.stderr, "Connection was refused."
            elif ex.errno == errno.ENOENT:
                print >> sys.stderr, "Unable to resolve address"
            else:
                print >> sys.stderr, "Socket %d: %s" % (ex.errno, ex.strerror)
        except xmlrpclib.ProtocolError as ex:
            print >> sys.stderr, "Unable to exchange XML-RPC message with dashboard server"
            print >> sys.stderr, "HTTP error code: %d/%s" % (ex.errcode, ex.errmsg)
        except xmlrpclib.Fault as ex:
            if ex.faultCode == 404:
                print >> sys.stderr, "Bundle stream %s does not exist" % (
                        pathname)
            elif ex.faultCode == 409:
                print >> sys.stderr, "You have already uploaded this bundle to the dashboard"
            else:
                print >> sys.stderr, "Unknown error"

