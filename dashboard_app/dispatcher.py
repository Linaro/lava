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
XML-RPC Dispatcher for the dashboard
"""
import SimpleXMLRPCServer
import logging
import sys
import xmlrpclib

class _NullHandler(logging.Handler):
    def emit(self, record):
        pass


class FaultCodes:
    """
    Common fault codes.

    See: http://xmlrpc-epi.sourceforge.net/specs/rfc.fault_codes.php
    """
    class ParseError:
        NOT_WELL_FORMED = -32700
        UNSUPPORTED_ENCODING = -32701
        INVALID_CHARACTER_FOR_ENCODING = -32702
    class ServerError:
        INVALID_XML_RPC = -32600
        REQUESTED_METHOD_NOT_FOUND = -32601
        INVALID_METHOD_PARAMETERS = -32602
        INTERNAL_XML_RPC_ERROR = -32603
    APPLICATION_ERROR = -32500
    SYSTEM_ERROR = -32400
    TRANSPORT_ERROR = -32300


class DjangoXMLRPCDispatcher(SimpleXMLRPCServer.SimpleXMLRPCDispatcher):
    """
    Slightly extended XML-RPC dispatcher class suitable for embedding in
    django applications.
    """
    #TODO: Implement _marshaled_dispatch() and capture XML errors to
    #      translate them to appropriate standardized fault codes. There
    #      might be some spill to the view code to make this complete.

    #TODO: Implement and expose system.getCapabilities() and advertise
    #      support for standardised fault codes.
    #      See: http://tech.groups.yahoo.com/group/xml-rpc/message/2897
    def __init__(self):
        # it's a classic class, no super
        SimpleXMLRPCServer.SimpleXMLRPCDispatcher.__init__(self,
                allow_none=True)
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(_NullHandler())

    def _lookup_func(self, method):
        """
        Lookup implementation of method named `method`.

        Returns implementation of `method` or None if the method is not
        registered anywhere in the dispatcher.

        This new function is taken directly out of the base class
        implementation of _dispatch. The point is to be able to
        detect a situation where method is not known and return
        appropriate XML-RPC fault. With plain dispatcher it is
        not possible as the implementation raises a plain Exception
        to signal this error condition and capturing and interpreting
        arbitrary exceptions is flaky.
        """
        func = None
        try:
            # check to see if a matching function has been registered
            func = self.funcs[method]
        except KeyError:
            if self.instance is not None:
                # check for a _dispatch method
                if hasattr(self.instance, '_dispatch'):
                    return self.instance._dispatch(method, params)
                else:
                    # call instance method directly
                    try:
                        func = SimpleXMLRPCServer.resolve_dotted_attribute(
                            self.instance,
                            method,
                            self.allow_dotted_names
                            )
                    except AttributeError:
                        pass
        return func

    def _dispatch(self, method, params):
        """
        Improved dispatch method from the base dispatcher.

        The primary improvement is exception handling:
            - xml-rpc faults are passed back to the caller
            - missing methods return standardized fault code (
              FaultCodes.ServerError.REQUESTED_METHOD_NOT_FOUND)
            - all other exceptions in the called method are translated
              to standardized internal xml-rpc fault code
              (FaultCodes.ServerError.INTERNAL_XML_RPC_ERROR).  In
              addition such errors cause _report_incident() to be
              called. This allows to hook a notification mechanism for
              deployed servers where exceptions are, for example, mailed
              to the administrator.
        """
        func = self._lookup_func(method)
        if func is None:
            raise xmlrpclib.Fault(
                    FaultCodes.ServerError.REQUESTED_METHOD_NOT_FOUND,
                    "No such method: %r" % method)
        try:
            # TODO: check parameter types before calling
            return func(*params)
        except xmlrpclib.Fault, fault:
            # Forward XML-RPC Faults to the client
            raise
        except:
            # Treat all other exceptions as internal errors 
            # This prevents the clients from seeing internals    
            exc_type, exc_value, exc_tb = sys.exc_info()
            incident_id = self._report_incident(method, params, exc_type, exc_value, exc_tb)
            string = ("Dashboard has encountered internal error. "
                    "Incident ID is: %s" % (incident_id,))
            raise xmlrpclib.Fault(
                    FaultCodes.ServerError.INTERNAL_XML_RPC_ERROR,
                    string)

    def _report_incident(self, method, params, exc_type, exc_value, exc_tb):
        """
        Report an exception that happened
        """
        self.logger.exception("Internal error when dispatching "
                "XML-RPC method: %s%r", method, params)
        # TODO: store the exception somewhere and assign fault codes 
        return None

    def system_methodSignature(self, method):
        if method.startswith("_"):
            return ""
        if self.instance is not None:
            func = getattr(self.instance, method, None)
        else:
            func = self.funcs.get(method)
        # When function is not known return empty string
        if func is None:
            return ""
        # When signature is not known return "undef"
        # See: http://xmlrpc-c.sourceforge.net/introspection.html
        return getattr(func, 'xml_rpc_signature', "undef")


def xml_rpc_signature(*sig):
    """
    Small helper that attaches "xml_rpc_signature" attribute to the
    function. The attribute is a list of values that is then reported
    by system_methodSignature().

    This is a simplification of the XML-RPC spec that allows to attach a
    list of variants (like I may accept this set of arguments, or that
    set or that other one). This version has only one set of arguments.

    Note that it's a purely presentational argument for our
    implementation. Putting bogus values here won't spoil the day.

    The first element is the signature of the return type.
    """
    def decorator(func):
        func.xml_rpc_signature = sig
        return func
    return decorator
