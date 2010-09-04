"""
Module with command-line tool commands that interact with the dashboard
server. All commands listed here should have counterparts in
the ..xml_rpc.commands package.
"""

import errno
import os
import socket
import urlparse
import xmlrpclib

from launch_control.commands.interface import Command

class XMLRPCCommand(Command):
    """
    Abstract base class for commands that interact with dashboard server
    over XML-RPC.

    The only difference is that you should implement invoke_remote()
    instead of invoke(). The provided implementation catches several
    socket and XML-RPC errors and prints a pretty error message.
    """

    __abstract__ = True

    def __init__(self, parser, args):
        super(XMLRPCCommand, self).__init__(parser, args)
        parts = urlparse.urlsplit(args.dashboard_url)
        if args.username and args.password:
            netloc = "%s:%s@%s" % (
                    args.username, args.password,
                    parts.netloc)
        else:
            netloc = parts.netloc
        urltext = urlparse.urlunsplit((parts.scheme, netloc, "/xml-rpc/",
                "", ""))
        self.server = xmlrpclib.ServerProxy(urltext, use_datetime=True,
                allow_none=True, verbose=args.verbose_xml_rpc)

    @classmethod
    def register_arguments(cls, parser):
        group = parser.add_argument_group("Dashboard Server options")
        group.add_argument('-u', '--username', default=None,
                help="Dashboard user name")
        group.add_argument('-p', '--password', default=None,
                help="Dashboard password")
        group.add_argument("--dashboard-url",
                default = "http://localhost:8000/",
                help="URL of your validation dashboard")
        group.add_argument("--verbose-xml-rpc",
                action="store_true", default=False,
                help="Show XML-RPC data")

    def invoke(self):
        try:
            self.invoke_remote()
        except socket.error as ex:
            print "Unable to connect to server at %s" % (
                    self.args.dashboard_url,)
            # It seems that some errors are reported as -errno
            # while others as +errno.
            if ex.errno < 0:
                ex.errno = -ex.errno
            if ex.errno == errno.ECONNREFUSED:
                print "Connection was refused"
            elif ex.errno == errno.ENOENT:
                print "Unable to resolve address"
            else:
                print "Socket %d: %s" % (ex.errno, ex.strerror)
        except xmlrpclib.Fault as ex:
            code = ex.faultCode
            if code == 1:
                print "Dashboard server has experienced internal error"
                print ex.faultString
            else:
                print "XML-RPC error %d: %s" % (ex.faultCode, ex.faultString)

    def invoke_remote(self):
        raise NotImplementedError()


class server_version(XMLRPCCommand):
    """
    Display dashboard server version
    """

    __abstract__ = False

    def invoke_remote(self):
        print "Dashboard server version: %s" % (self.server.version(),)
