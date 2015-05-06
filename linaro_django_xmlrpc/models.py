# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Linaro Django XMLRPC.
#
# Linaro Django XMLRPC is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Linaro Django XMLRPC is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Linaro Django XMLRPC.  If not, see <http://www.gnu.org/licenses/>.

"""
Empty module for Django to pick up this package as Django application
"""

import datetime
import inspect
import logging
import random
import xmlrpclib

from django.contrib.auth.models import User
from django.db import models


class AuthToken(models.Model):
    """
    Authentication token.

    Used by the AuthTokenBackend to associate a request with user.  Similar to
    OAuth resource token but much more primitive, based on HTTP Basic Auth.
    """

    # Set of valid characters for secret
    _SECRET_CHARS = "01234567890abcdefghijklmnopqrtsuwxyz"

    secret = models.CharField(
        max_length=128,
        help_text=("Secret randomly generated text that grants user access "
                   "instead of their regular password"),
        unique=True,
        default=lambda: ''.join((random.choice(AuthToken._SECRET_CHARS)
                                 for i in xrange(128))))

    description = models.TextField(
        default="",
        null=False,
        blank=True,
        help_text=("Arbitrary text that helps the user to associate tokens "
                   "with their intended purpose"))

    created_on = models.DateTimeField(
        auto_now=True,
        help_text="Time and date when the token was created")

    last_used_on = models.DateTimeField(
        null=True,
        help_text="Time and date when the token was last used")

    user = models.ForeignKey(User, related_name="auth_tokens")

    def __unicode__(self):
        return u"security token {pk}".format(pk=self.pk)

    @classmethod
    def get_user_for_secret(cls, username, secret):
        """
        Lookup an user for this secret, returns None on failure.

        This also bumps last_used_on if successful
        """
        try:
            token = cls.objects.get(secret=secret)
        except cls.DoesNotExist:
            return None
        else:
            if token.user.username != username:
                return None  # bad username for this secret
            token.last_used_on = datetime.datetime.utcnow()
            token.save()
            return token.user


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
        func.xml_rpc_signature = list(sig)
        return func
    return decorator


class FaultCodes(object):
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


class CallContext(object):
    """
    Call context encapsulates all runtime information about a particular call
    to ExposedAPI subclasses. In practice it binds the user, mapper and
    dispatcher together.
    """

    def __init__(self, user, mapper, dispatcher, request=None):
        if user is not None and user.is_authenticated() and user.is_active:
            self._user = user
        else:
            self._user = None
        self._mapper = mapper
        self._dispatcher = dispatcher
        self._request = request

    @property
    def user(self):
        """
        Return the user making the request.

        The use of authentication tokens means that this can be different to
        request.user.
        """
        return self._user

    @property
    def mapper(self):
        """
        Return the XML-RPC mapper.

        Mapper provides a binding between method names and ExposedAPI classes.
        It is normally only needed in special situations, such as when
        implementing SystemAPI class.
        """
        return self._mapper

    @property
    def dispatcher(self):
        """
        Return the XML-RPC dispatcher object.

        Dispatcher provides a mechanism for invoking XML-RPC methods. It is
        normally only needed in special situations, such as when implementing
        SystemAPI class.
        """
        return self._dispatcher

    @property
    def request(self):
        """
        Return the HttpRequest object.

        Generally, you won't need to look at this -- the dispatcher will have
        interpreted the post data and so on.  But sometimes it's essential.
        """
        return self._request


class ExposedAPI(object):
    """
    Base class for exposing code via XML-RPC.

    To use inherit from this class and add public methods (not prefixed
    with _). Each method should have a sensible docstring as it will be
    exposed to developers accessing your services.

    To work with authentication you can inspect the user instance
    variable. If the request was authenticated using any available
    authentication method the instance variable will point to a
    django.contrib.auth.models.User instance. You will _never_ get
    AnonymousUser or users with is_active=False, those are replaced by
    None automatically.
    """

    def __init__(self, context=None):
        if context is not None and not isinstance(context, CallContext):
            raise TypeError(
                "context must be a subclass of CallContext (got %r)" % context)
        self._context = context

    @property
    def user(self):
        if self._context is not None:
            return self._context.user
        else:
            return None

    def _authenticate(self):
        if self.user is None:
            raise xmlrpclib.Fault(
                401, "Authentication with user and token required for this "
                "API.")

    def _switch_user(self, username):
        """
        Allow a superuser to query a different user
        """
        if not username:
            return self.user
        if self.user.is_superuser:
            try:
                username = User.objects.get(username=username)
            except User.DoesNotExist:
                raise xmlrpclib.Fault(
                    404, "Username %s not found" % username)
        else:
            raise xmlrpclib.Fault(
                401,
                "Permission denied for user '%s' to query other users" % self.user)
        return username


class Mapper(object):
    """
    Simple namespace for mapping multiple subclasses of ExposedAPI using one
    dispatcher.

    >>> class Hello(ExposedAPI):
    ...     def world(self):
    ...         return "hi"

    The mapper is then used by dispatcher to lookup methods.
    >>> mapper = Mapper()
    >>> mapper.register(Hello)

    The lookup method allows to get callable thing matching the
    specified XML-RPC method name.
    >>> func = mapper.lookup('Hello.world')
    >>> func()
    "hi"
    """

    def __init__(self):
        self.registered = {}

    def register(self, cls, name=None):
        """
        Expose specified object or class under specified name

        Name defaults to the name of the class.
        """
        if not isinstance(cls, type) or not issubclass(cls, ExposedAPI):
            raise TypeError(
                "Only ExposedAPI subclasses can be registered with the mapper")
        if name is None:
            name = cls.__name__
        if name in self.registered:
            raise ValueError(
                "Name %r is already registered with this mapper" % name)
        self.registered[name] = cls

    def lookup(self, name, context=None):
        """
        Lookup the callable associated with the specified name.

        The callable is a bound method of a registered object or a bound
        method of a freshly instantiated object of a registered class.

        @return A callable or None if the name does not designate any
        registered entity.
        """
        if "." in name:
            api_name, meth_name = name.split('.', 1)
        else:
            meth_name = name
            api_name = ''
        if meth_name.startswith("_"):
            return
        cls = self.registered.get(api_name)
        if cls is None:
            return
        try:
            obj = cls(context)
        except:
            # TODO: Perhaps this should be an APPLICATION_ERROR?
            logging.exception("unable to instantiate API class %r", cls)
            obj = None
        meth = getattr(obj, meth_name, None)
        if not inspect.ismethod(meth):
            return
        return meth

    def list_methods(self):
        """
        Calculate a sorted list of registered methods.

        Each method is exposed either from the root object or from a single
        level hierarchy of named objects. For example:

        'system.listMethods' is a method exposed from the 'system' object
        'version' is a method exposed from the root object.

        @return A list of sorted method names
        """
        methods = []
        for register_path in self.registered:
            cls = self.registered[register_path]
            for method_name, impl in inspect.getmembers(cls, inspect.ismethod):
                if method_name.startswith("_"):
                    continue
                if register_path:
                    methods.append(register_path + "." + method_name)
                else:
                    methods.append(method_name)
        methods.sort()
        return methods

    def register_introspection_methods(self):
        """
        Register SystemAPI as 'system' object.

        This method is similar to the SimpleXMLRPCServer method with the same
        name. It exposes several standard XML-RPC methods that make it
        possible to introspect all exposed methods.

        For reference see the SystemAPI class.
        """
        self.register(SystemAPI, 'system')


class Dispatcher(object):
    """
    XML-RPC dispatcher based on Mapper (for name lookup) and libxmlrpc (for
    marshalling). The API is loosely modeled after SimpleXMLRPCDispatcher from
    the standard python library but methods are not private and take
    additional arguments that allow for user authentication.

    Unlike the original server this server does not expose errors in the
    internal method implementation unless those errors are raised as
    xmlrpclib.Fault instances.

    Subclasses may want to override handle_internal_error() that currently
    uses logging.exception to print as short message.
    """

    def __init__(self, mapper, allow_none=True):
        self.mapper = mapper
        self.allow_none = allow_none
        self.logger = logging.getLogger()

    def decode_request(self, data):
        """
        Decode marshalled XML-RPC message.

        @return A tuple with (method_name, params)
        """
        # TODO: Check that xmlrpclib.loads can only raise this exception (it
        # probably can raise some others as well but this is not documented)
        # and handle each by wrapping it into an appropriate Fault with correct
        # code/message.
        try:
            params, method_name = xmlrpclib.loads(data)
            return method_name, params
        except xmlrpclib.ResponseError:
            raise xmlrpclib.Fault(
                FaultCodes.ServerError.INVALID_XML_RPC,
                "Unable to decode request")
        except:
            raise xmlrpclib.Fault(
                FaultCodes.ServerError.INTERNAL_XML_RPC_ERROR,
                "Unable to decode request")

    def marshalled_dispatch(self, data, user=None, request=None):
        """
        Dispatch marshalled request (encoded with XML-RPC envelope).

        This is the entry point to the Dispatcher API.

        Returns the text of the response
        """
        context = CallContext(
            user, mapper=self.mapper, dispatcher=self, request=request)
        try:
            method_name, params = self.decode_request(data)
            response = self.dispatch(method_name, params, context)
        except xmlrpclib.Fault as fault:
            # Push XML-RPC faults to the client
            response = xmlrpclib.dumps(fault, allow_none=self.allow_none)
        else:
            # Package responses and send them to the client
            response = (response,)
            response = xmlrpclib.dumps(
                response, methodresponse=1, allow_none=self.allow_none)
        return response

    def dispatch(self, method_name, params, context):
        """
        Dispatch method with the specified name, parameters and context
        """
        try:
            impl = self.mapper.lookup(method_name, context)
            if impl is None:
                self.logger.error(
                    'Unable to dispatch unknown method %r', method_name,
                    extra={'request': context.request})
                raise xmlrpclib.Fault(FaultCodes.ServerError.REQUESTED_METHOD_NOT_FOUND,
                                      "No such method: %r" % method_name)
            # TODO: check parameter types before calling
            return impl(*params)
        except xmlrpclib.Fault:
            # Forward XML-RPC Faults to the client
            raise
        except Exception as e:
            # Call a helper than can do more
            if self.handle_internal_error(method_name, params) is None:
                # If there is no better handler we should log the problem
                self.logger.error(
                    "Internal error in the XML-RPC dispatcher while calling method %r with %r",
                    method_name, params, exc_info=True,
                    extra={'request': context.request})
            # TODO: figure out a way to get the error id from Raven if that is around
            raise xmlrpclib.Fault(
                FaultCodes.ServerError.INTERNAL_XML_RPC_ERROR,
                "Internal Server Error (details hidden :) %s" % e)

    def handle_internal_error(self, method_name, params):
        """
        Handle exceptions raised while dispatching registered methods.

        Subclasses may implement this but cannot prevent the xmlrpclib.Fault
        from being raised. If something other than None is returned then a
        logging message will be supressed.
        """
        return None


class SystemAPI(ExposedAPI):
    """
    XML-RPC System API

    This API may be mapped as "system" object to conform to XML-RPC
    introspection specification.
    """

    def __init__(self, context):
        if context is None:
            raise ValueError(
                "SystemAPI needs to be constructed with a real CallContext")
        super(SystemAPI, self).__init__(context)

    def listMethods(self):
        """
        Name
        ----
        `listMethods` ()

        Description
        -----------
        List all available methods in this XML-RPC server.

        Arguments
        ---------
        None

        Return value
        ------------
        Returns a list of available methods.
        """
        return self._context.mapper.list_methods()

    def methodSignature(self, method_name):
        """
        Name
        ----
        `methodSignature` (`method_name`)

        Description
        -----------
        Provide signature for the specified method.

        Arguments
        ---------
        `method_name`: string
            Name of the method whose signature is required.

        Return value
        ------------
        Returns the signature for specified method or undef if the signature is
        unknown.
        """
        impl = self._context.mapper.lookup(method_name, self._context)
        if impl is None:
            return ""
        # When signature is not known return "undef"
        # See: http://xmlrpc-c.sourceforge.net/introspection.html
        return getattr(impl, 'xml_rpc_signature', "undef")

    @xml_rpc_signature('str', 'str')
    def methodHelp(self, method_name):
        """
        Name
        ----
        `methodHelp` (`method_name`)

        Description
        -----------
        Provide documentation for specified method.

        Arguments
        ---------
        `method_name`: string
            Name of the method whose documentation is required.

        Return value
        ------------
        Returns the documentation for specified method.
        """
        impl = self._context.mapper.lookup(method_name, self._context)
        if impl is None:
            return ""
        else:
            import pydoc
            return pydoc.getdoc(impl)

    def _multicall_dispatch_one(self, subcall):
        """
        Dispatch one multicall request
        """
        if not isinstance(subcall, dict):
            return xmlrpclib.Fault(
                FaultCodes.ServerError.INVALID_METHOD_PARAMETERS,
                "system.multicall expected struct")
        if 'methodName' not in subcall:
            return xmlrpclib.Fault(
                FaultCodes.ServerError.INVALID_METHOD_PARAMETERS,
                "system.multicall methodName not specified")
        methodName = subcall.pop('methodName')
        if not isinstance(methodName, basestring):
            return xmlrpclib.Fault(
                FaultCodes.ServerError.INVALID_METHOD_PARAMETERS,
                "system.multicall methodName must be a string")
        if 'params' not in subcall:
            return xmlrpclib.Fault(
                FaultCodes.ServerError.INVALID_METHOD_PARAMETERS,
                "system.multicall params not specified")
        params = subcall.pop('params')
        if not isinstance(params, list):
            return xmlrpclib.Fault(
                FaultCodes.ServerError.INVALID_METHOD_PARAMETERS,
                "system.multicall params must be an array")
        if len(subcall) > 0:
            return xmlrpclib.Fault(
                FaultCodes.ServerError.INVALID_METHOD_PARAMETERS,
                "system.multicall specified additional arguments %s" %
                sorted(subcall.keys()))
        try:
            return self._context.dispatcher.dispatch(
                methodName, params, self._context)
        except xmlrpclib.Fault as fault:
            return fault

    @xml_rpc_signature('array', 'array')
    def multicall(self, subcalls):
        """
        Call multiple methods with one request.

        See: http://web.archive.org/web/20060824100531/http://www.xmlrpc.com/discuss/msgReader$1208

        The calls are specified by an XML-RPC array of XML-RPC structures.
        Each structure must have exactly two arguments: 'methodName' and
        'params'. Method name must be a string matching existing method.
        Params must be an XML-RPC array of arguments for that method.

        All methods will be executed in order, failure of any method does not
        prevent other methods from executing.

        The return value is an XML-RPC array of the same length as the lenght
        of the subcalls array. Each element of the result array holds either an
        XML-RPC Fault when the subcall has failed or a list with one element
        that is the return value of the subcall.
        """
        if not isinstance(subcalls, list):
            raise xmlrpclib.Fault(
                FaultCodes.ServerError.INVALID_METHOD_PARAMETERS,
                "system.multicall expected a list of methods to call")
        results = []
        for subcall in subcalls:
            result = self._multicall_dispatch_one(subcall)
            if isinstance(result, xmlrpclib.Fault):
                # Faults are returned directly
                results.append(result)
            else:
                # We need to box each return value  in a list to distinguish
                # them from faults which will be encoded as XML-RPC structs and
                # might be indistinguishable from successul calls returning an
                # XML-RCP struct.
                results.append([result])
        return results

    def getCapabilities(self):
        """
        Name
        ----
        `getCapabilities` ()

        Description
        -----------
        XML-RPC Server capabilities.

        Arguments
        ---------
        None

        Return value
        ------------
        Returns the XML-RPC Server capabilities which has the following format:

        {
          auth_token: {
            'specUrl': 'xxxxxx',
            'specVersion': xxxxxx
          },
          'introspect': {
            'specUrl': 'xxxxxx',
            'specVersion': x
          },
          'faults_interop': {
            'specUrl': 'xxxxxx',
            'specVersion': xxxxxx
          }
        }

        Reference
        ---------
        * See: http://groups.yahoo.com/group/xml-rpc/message/2897

        * http://xmlrpc-c.sourceforge.net/xmlrpc-c/introspection.html is dead,
        the actual URL that works is:
        http://xmlrpc-c.sourceforge.net/introspection.html This is, however,
        what the spec mandates (visit the URL above to cross-reference the
        relevant fragment).
        """
        return {
            "introspect": {
                "specUrl": "http://xmlrpc-c.sourceforge.net/xmlrpc-c/introspection.html",
                "specVersion": 1
            },
            "faults_interop": {
                "specUrl": "http://xmlrpc-epi.sourceforge.net/specs/rfc.fault_codes.php",
                "specVersion": 20010516
            },
            "auth_token": {
                # XXX: We need some good way to indicate we support token
                # authentication Month and date is actually taken from the time
                # this spec was registered in lanuchpad. It was was *not*
                # copy-pasted from fault codes spec :-)
                "specUrl": "https://blueprints.launchpad.net/linaro-django-xmlrpc/+spec/other-o-linaro-xml-rpc-auth-tokens",
                "specVersion": 20110516
            }
        }
