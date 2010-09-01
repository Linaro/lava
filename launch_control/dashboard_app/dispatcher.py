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


class DjangoXMLRPCDispatcher(SimpleXMLRPCServer.SimpleXMLRPCDispatcher):
    """
    Slightly extended XML-RPC dispatcher class suitable for embedding in
    django applications.
    """
    def __init__(self):
        # it's a classic class, no super
        SimpleXMLRPCServer.SimpleXMLRPCDispatcher.__init__(self,
                allow_none=True)
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(_NullHandler())

    def _dispatch(self, method, params):
        try:
            return SimpleXMLRPCServer.SimpleXMLRPCDispatcher._dispatch(self, method, params)
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
            raise xmlrpclib.Fault(1, string)

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
