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
Unit tests for Linaro Django XML-RPC Application
"""
import re
import xmlrpclib

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django_testscenarios.ubertest import TestCase, TestCaseWithScenarios

from linaro_django_xmlrpc.models import (
    AuthToken,
    CallContext,
    Dispatcher,
    ExposedAPI,
    FaultCodes,
    Mapper,
    SystemAPI,
    xml_rpc_signature,
)


class MockUser(object):
    """
    Mock django.contrib.auth.models.User class for our test cases
    """

    def __init__(self, is_authenticated, is_active):
        self._is_active = is_active
        self._is_authenticated = is_authenticated

    @property
    def is_active(self):
        return self._is_active

    def is_authenticated(self):
        return self._is_authenticated


class ExampleAPI(ExposedAPI):
    """
    Fake API for our tests
    """

    @xml_rpc_signature("str")
    def foo(self):
        """foo docstring"""
        return "bar"

    def bar(self):
        return "foo"


class CallContextTests(TestCase):

    def test_unauthenticated_users_are_ignored(self):
        user = MockUser(is_authenticated=False, is_active=True)
        context = CallContext(user, None, None)
        self.assertEqual(context.user, None)

    def test_inactive_users_are_ignored(self):
        user = MockUser(is_authenticated=True, is_active=False)
        context = CallContext(user, None, None)
        self.assertEqual(context.user, None)

    def test_authenticated_active_users_are_allowed(self):
        user = MockUser(is_authenticated=True, is_active=True)
        context = CallContext(user, None, None)
        self.assertEqual(context.user, user)


class ExposedAPITests(TestCase):

    def test_context_must_be_of_proper_clasS(self):
        self.assertRaises(TypeError, ExposedAPI, object())

    def test_context_defaults_to_None(self):
        api = ExposedAPI()
        self.assertIs(api._context, None)

    def test_without_context_user_is_None(self):
        api = ExposedAPI()
        self.assertIs(api.user, None)

    def test_user_returns_context_user(self):
        user = MockUser(True, True)
        context = CallContext(user, None, None)
        api = ExposedAPI(context)
        self.assertIs(api.user, context.user)


class MapperTests(TestCase):

    def setUp(self):
        super(MapperTests, self).setUp()
        self.mapper = Mapper()

    def test_register_checks_type(self):
        self.assertRaises(TypeError, self.mapper.register, object)

    def test_register_guesses_class_name(self):
        self.mapper.register(ExampleAPI)
        self.assertTrue("ExampleAPI" in self.mapper.registered)

    def test_register_respects_explicit_class_name(self):
        self.mapper.register(ExampleAPI, "example_api")
        self.assertTrue("example_api" in self.mapper.registered)

    def test_register_prevents_overwrites_of_previous_binding(self):
        class TestAPI1(ExposedAPI):
            pass

        class TestAPI2(ExposedAPI):
            pass
        self.mapper.register(TestAPI1, 'API')
        self.assertRaises(ValueError, self.mapper.register, TestAPI2, 'API')
        self.assertTrue('API' in self.mapper.registered)
        self.assertTrue(self.mapper.registered['API'] is TestAPI1)

    def test_lookup_finds_method(self):
        self.mapper.register(ExampleAPI)
        foo = self.mapper.lookup("ExampleAPI.foo")
        # Calling the method is easier than doing some other magic here
        self.assertEqual(foo(), "bar")

    def test_lookup_finds_method_in_root_scope(self):
        self.mapper.register(ExampleAPI, '')
        foo = self.mapper.lookup("foo")
        # Calling the method is easier than doing some other magic here
        self.assertEqual(foo(), "bar")

    def test_lookup_returns_none_if_method_not_found(self):
        self.mapper.register(ExampleAPI)
        retval = self.mapper.lookup("ExampleAPI.missing_method")
        self.assertEqual(retval, None)

    def test_lookup_returns_none_if_object_or_class_not_found(self):
        retval = self.mapper.lookup("ExampleAPI.foo")
        self.assertEqual(retval, None)

    def test_lookup_passes_context_to_exposed_api(self):
        class TestAPI(ExposedAPI):

            def foo(self):
                pass
        self.mapper.register(TestAPI, 'API')
        context = CallContext(None, self.mapper, None)
        retval = self.mapper.lookup('API.foo', context)
        # bound method seems to have im_self attribute pointing back to self
        self.assertIs(retval.im_self._context, context)

    def test_list_methods_without_methods(self):
        class TestAPI(ExposedAPI):
            pass
        self.mapper.register(TestAPI)
        retval = self.mapper.list_methods()
        self.assertEqual(retval, [])

    def test_list_methods_from_global_scope(self):
        class TestAPI(ExposedAPI):
            def a(self):
                pass

            def b(self):
                pass

            def c(self):
                pass
        self.mapper.register(TestAPI, '')
        retval = self.mapper.list_methods()
        self.assertEqual(retval, ['a', 'b', 'c'])

    def test_list_methods_from_class_scope(self):
        class TestAPI(ExposedAPI):
            def a(self):
                pass

            def b(self):
                pass

            def c(self):
                pass
        self.mapper.register(TestAPI)
        retval = self.mapper.list_methods()
        self.assertEqual(retval, ['TestAPI.a', 'TestAPI.b', 'TestAPI.c'])

    def test_list_methods_with_two_sources(self):
        class SourceA(ExposedAPI):
            def a(self):
                pass

        class SourceB(ExposedAPI):
            def a(self):
                pass
        self.mapper.register(SourceA)
        self.mapper.register(SourceB)
        retval = self.mapper.list_methods()
        self.assertEqual(retval, ['SourceA.a', 'SourceB.a'])


class TestAPI(ExposedAPI):
    """
    Test API that gets exposed by the dispatcher for test runs.
    """

    def ping(self):
        """
        Return "pong" message
        """
        return "pong"

    def echo(self, arg):
        """
        Return the argument back to the caller
        """
        return arg

    def boom(self, code, string):
        """
        Raise a Fault exception with the specified code and string
        """
        raise xmlrpclib.Fault(code, string)

    def internal_boom(self):
        """
        Raise a regular python exception (this should be hidden behind
        an internal error fault)
        """
        raise Exception("internal boom")


class DispatcherTests(TestCase):

    def setUp(self):
        super(DispatcherTests, self).setUp()
        self.mapper = Mapper()
        self.mapper.register(TestAPI, '')
        self.dispatcher = Dispatcher(self.mapper)

    def xml_rpc_call(self, method, *args):
        """
        Perform XML-RPC call on our internal dispatcher instance

        This calls the method just like we would have normally from our view.
        All arguments are marshaled and un-marshaled. XML-RPC fault exceptions
        are raised like normal python exceptions (by xmlrpclib.loads)
        """
        request = xmlrpclib.dumps(tuple(args), methodname=method)
        response = self.dispatcher.marshalled_dispatch(request)
        # This returns return value wrapped in a tuple and method name
        # (which we don't have here as this is a response message).
        return xmlrpclib.loads(response)[0][0]

    def test_standard_fault_code_for_method_not_found(self):
        try:
            self.xml_rpc_call("method_that_does_not_exist")
        except xmlrpclib.Fault as ex:
            self.assertEqual(
                ex.faultCode,
                FaultCodes.ServerError.REQUESTED_METHOD_NOT_FOUND)
        else:
            self.fail("Calling missing method did not raise an exception")

    def test_internal_error_handler_is_called_on_exception(self):
        self.was_called = False

        def handler(method, params):
            self.assertEqual(method, 'internal_boom')
            self.assertEqual(params, ())
            self.was_called = True
        self.dispatcher.handle_internal_error = handler
        try:
            self.xml_rpc_call("internal_boom")
        except xmlrpclib.Fault:
            pass
        else:
            self.fail("Exception not raised")
        self.assertTrue(self.was_called)

    def test_standard_fault_code_for_internal_error(self):
        # This handler is here just to prevent the default one from
        # spamming the console with the error that is raised inside the
        # internal_boom() method
        self.dispatcher.handle_internal_error = lambda method, args: None
        try:
            self.xml_rpc_call("internal_boom")
        except xmlrpclib.Fault as ex:
            self.assertEqual(
                ex.faultCode,
                FaultCodes.ServerError.INTERNAL_XML_RPC_ERROR)
        else:
            self.fail("Exception not raised")

    def test_ping(self):
        retval = self.xml_rpc_call("ping")
        self.assertEqual(retval, "pong")

    def test_echo(self):
        self.assertEqual(self.xml_rpc_call("echo", 1), 1)
        self.assertEqual(self.xml_rpc_call("echo", "string"), "string")
        self.assertEqual(self.xml_rpc_call("echo", 1.5), 1.5)

    def test_boom(self):
        self.assertRaises(xmlrpclib.Fault,
                          self.xml_rpc_call, "boom", 1, "str")


class SystemAPITest(TestCase):

    def setUp(self):
        super(SystemAPITest, self).setUp()
        self.mapper = Mapper()
        self.dispatcher = Dispatcher(self.mapper)
        self.context = CallContext(
            user=None, mapper=self.mapper, dispatcher=self.dispatcher)
        self.system_api = SystemAPI(self.context)

    def test_listMethods_just_calls_mapper_list_methods(self):
        obj = object()
        self.mapper.list_methods = lambda: obj
        retval = self.system_api.listMethods()
        self.assertEqual(retval, obj)

    def test_methodHelp_returns_blank_when_method_has_no_docstring(self):
        class TestAPI(ExposedAPI):
            def method(self):
                pass
        self.mapper.register(TestAPI)
        retval = self.system_api.methodHelp("TestAPI.method")
        self.assertEqual(retval, "")

    def test_methodHelp_returns_the_docstring(self):
        class TestAPI(ExposedAPI):
            def method(self):
                """docstring"""
        self.mapper.register(TestAPI)
        retval = self.system_api.methodHelp("TestAPI.method")
        self.assertEqual(retval, "docstring")

    def test_methodHelp_strips_the_leading_whitespce(self):
        class TestAPI(ExposedAPI):
            def method(self):
                """
                line 1
                line 2
                """
        self.mapper.register(TestAPI)
        retval = self.system_api.methodHelp("TestAPI.method")
        self.assertEqual(retval, "line 1\nline 2")

    def test_methodSignature_returns_undef_by_default(self):
        class TestAPI(ExposedAPI):
            def method(self):
                pass
        self.mapper.register(TestAPI)
        retval = self.system_api.methodSignature("TestAPI.method")
        self.assertEqual(retval, 'undef')

    def test_methodSignature_returns_signature_when_defined(self):
        class TestAPI(ExposedAPI):
            @xml_rpc_signature('str', 'int')
            def int_to_str(value):
                return "%s" % value
        self.mapper.register(TestAPI)
        retval = self.system_api.methodSignature("TestAPI.int_to_str")
        self.assertEqual(retval, ['str', 'int'])

    def test_multicall_with_empty_list(self):
        retval = self.system_api.multicall([])
        self.assertEqual(retval, [])

    def test_multicall_boxes_normal_return_values_in_lists(self):
        # The return value of multicall is more complex than one might
        # originally think: each return value is boxed in a one-element list
        # to be different from unboxed faults.
        class TestAPI(ExposedAPI):

            def foo(self):
                return 1
        self.mapper.register(TestAPI)
        calls = [
            {"methodName": "TestAPI.foo", "params": []},
        ]
        observed = self.system_api.multicall(calls)
        self.assertIsInstance(observed[0], list)
        self.assertEqual(observed, [[1]])

    def test_multicall_calls_methods(self):
        class TestAPI(ExposedAPI):

            def foo(self):
                return "foo-result"

            def bar(self, arg):
                return arg
        self.mapper.register(TestAPI)
        calls = [
            {"methodName": "TestAPI.foo", "params": []},
            {"methodName": "TestAPI.bar", "params": ["bar-result"]},
        ]
        expected = [
            ["foo-result"],
            ["bar-result"]
        ]
        observerd = self.system_api.multicall(calls)
        self.assertEqual(observerd, expected)

    def test_multicall_does_not_box_faults(self):
        # See comment in test_multicall_boxes_normal_return_values_in_lists
        # above. Each fault is returned directly and is not boxed in a list.
        class TestAPI(ExposedAPI):

            def boom(self):
                raise xmlrpclib.Fault(1, "boom")
        self.mapper.register(TestAPI)
        calls = [
            {"methodName": "TestAPI.boom", "params": []},
        ]
        observed = self.system_api.multicall(calls)
        self.assertIsInstance(observed[0], xmlrpclib.Fault)

    def test_multicall_just_returns_faults(self):
        # If one method being called returns a fault, any subsequent method
        # calls are still performed.
        class TestAPI(ExposedAPI):

            def boom(self):
                raise xmlrpclib.Fault(1, "boom")

            def echo(self, arg):
                return arg
        self.mapper.register(TestAPI)
        calls = [
            {"methodName": "TestAPI.echo", "params": ["before"]},
            {"methodName": "TestAPI.boom", "params": []},
            {"methodName": "TestAPI.echo", "params": ["after"]},
        ]
        observed = self.system_api.multicall(calls)
        # echo is called with 'before'
        self.assertEqual(observed[0], ["before"])
        # Note that at this point the exception is returned as-is. It will be
        # converted to proper xml-rpc encoding by the dispatcher. Here we do
        # manual comparison as xmlrpclib.Fault does not implement __eq__
        # properly.
        self.assertEqual(observed[1].faultCode, 1)
        self.assertEqual(observed[1].faultString, "boom")
        # echo is called with 'after'
        self.assertEqual(observed[2], ["after"])

    def test_multicall_wants_a_list_of_sub_calls(self):
        # XXX: Use TestCaseWithInvariants in the future
        for bad_stuff in [None, {}, True, False, -1, 10000, "foobar"]:
            try:
                self.system_api.multicall(bad_stuff)
            except xmlrpclib.Fault as ex:
                self.assertEqual(ex.faultCode, FaultCodes.ServerError.INVALID_METHOD_PARAMETERS)
                self.assertEqual(ex.faultString, "system.multicall expected a list of methods to call")
            else:
                self.fail("Should have raised an exception")

    def test_multicall_subcall_wants_a_dict(self):
        # XXX: Use TestCaseWithInvariants in the future
        for bad_stuff in [None, [], True, False, -1, 10000, "foobar"]:
            [result] = self.system_api.multicall([bad_stuff])
            self.assertIsInstance(result, xmlrpclib.Fault)
            self.assertEqual(
                result.faultCode,
                FaultCodes.ServerError.INVALID_METHOD_PARAMETERS)

    def test_multicall_subcall_wants_methodName(self):
        [result] = self.system_api.multicall([{}])
        self.assertIsInstance(result, xmlrpclib.Fault)
        self.assertEqual(
            result.faultCode,
            FaultCodes.ServerError.INVALID_METHOD_PARAMETERS)

    def test_multicall_subcall_wants_methodName_to_be_a_string(self):
        [result] = self.system_api.multicall(
            [{"methodName": False}])
        self.assertIsInstance(result, xmlrpclib.Fault)
        self.assertEqual(
            result.faultCode,
            FaultCodes.ServerError.INVALID_METHOD_PARAMETERS)

    def test_multicall_subcall_wants_params(self):
        [result] = self.system_api.multicall(
            [{"methodName": "system.listMethods"}])
        self.assertIsInstance(result, xmlrpclib.Fault)
        self.assertEqual(
            result.faultCode,
            FaultCodes.ServerError.INVALID_METHOD_PARAMETERS)

    def test_multicall_subcall_wants_params_to_be_a_list(self):
        [result] = self.system_api.multicall(
            [{"methodName": "system.listMethods", "params": False}])
        self.assertIsInstance(result, xmlrpclib.Fault)
        self.assertEqual(
            result.faultCode,
            FaultCodes.ServerError.INVALID_METHOD_PARAMETERS)

    def test_multicall_subcall_rejects_other_arguments(self):
        [result] = self.system_api.multicall(
            [{"methodName": "system.listMethods", "params": [], "other": 1}])
        self.assertIsInstance(result, xmlrpclib.Fault)
        print result.faultString
        self.assertEqual(
            result.faultCode,
            FaultCodes.ServerError.INVALID_METHOD_PARAMETERS)

    def test_listMethods_exists(self):
        self.mapper.register(SystemAPI, 'system')
        self.assertIn("system.listMethods", self.system_api.listMethods())

    def test_methodHelp_exists(self):
        self.mapper.register(SystemAPI, 'system')
        self.assertIn("system.methodHelp", self.system_api.listMethods())

    def test_methodSignature_exists(self):
        self.mapper.register(SystemAPI, 'system')
        self.assertIn("system.methodSignature", self.system_api.listMethods())

    def test_getCapabilities_exists(self):
        self.mapper.register(SystemAPI, 'system')
        self.assertIn("system.getCapabilities", self.system_api.listMethods())

    def test_multicall_exists(self):
        self.mapper.register(SystemAPI, 'system')
        self.assertIn("system.multicall", self.system_api.listMethods())

    def test_fault_interop_capabilitiy_supported(self):
        self.assertIn("faults_interop", self.system_api.getCapabilities())

    def test_auth_token_capability_supported(self):
        self.assertIn("auth_token", self.system_api.getCapabilities())

    def test_introspect_capability_supported(self):
        self.assertIn("introspect", self.system_api.getCapabilities())


class HandlerAuthTests(TestCaseWithScenarios):

    scenarios = [
        ('no_space_in_http_authorization', {
            'HTTP_AUTHORIZATION': "no_space_here",
            'text': "Invalid HTTP_AUTHORIZATION header",
            'status_code': 400,
        }),
        ('not_basic_auth', {
            'HTTP_AUTHORIZATION': "Bogus foobar",
            'text': "Unsupported HTTP_AUTHORIZATION header, only Basic scheme is supported",
            'status_code': 400,
        }),
        ('bad_base64_header', {
            'HTTP_AUTHORIZATION': "Basic XNlcjp0b2tlbg==",  # 'user:token' encoded, first character removed ('d')
            'text': "Corrupted HTTP_AUTHORIZATION header, bad base64 encoding",
            'status_code': 400,
        }),
        ('no_user_colon_pass', {
            'HTTP_AUTHORIZATION': "Basic dXNlcnRva2Vu",  # 'usertoken' encoded
            'text': "Corrupted HTTP_AUTHORIZATION header, no user:pass",
            'status_code': 400,
        }),
        ('invalid_token', {
            'HTTP_AUTHORIZATION': "Basic dXNlcjp0b2tlbg==",  # 'user:token' encoded
            'text': "Invalid token",
            'status_code': 401,
        }),
    ]

    def setUp(self):
        super(HandlerAuthTests, self).setUp()
        self.request_data = xmlrpclib.dumps((), methodname="system.listMethods")
        self.url = reverse("linaro_django_xmlrpc.views.default_handler")

    def test_invalid_http_authorization_header(self):
        response = self.client.post(
            self.url, data=self.request_data,
            content_type="text/xml",
            HTTP_AUTHORIZATION=self.HTTP_AUTHORIZATION)
        self.assertContains(response, text=self.text, status_code=self.status_code)


class AuthTokenTests(TestCase):

    _USER = "user"
    _INEXISTING_USER = "inexisting-user"
    _INEXISTING_SECRET = "inexisting-secret"

    def setUp(self):
        super(AuthTokenTests, self).setUp()
        self.user = User.objects.get_or_create(username=self._USER)[0]

    def test_secret_is_generated(self):
        token = AuthToken.objects.create(user=self.user)
        self.assertTrue(re.match("[a-z0-9]{128}", token.secret))

    def test_generated_secret_is_not_constant(self):
        token1 = AuthToken.objects.create(user=self.user)
        token2 = AuthToken.objects.create(user=self.user)
        self.assertNotEqual(token1.secret, token2.secret)

    def test_created_on(self):
        token = AuthToken.objects.create(user=self.user)
        self.assertTrue(token.created_on is not None)
        # XXX: How to sensibly test auto_now? aka how to mock time

    def test_last_used_on_is_initially_empty(self):
        token = AuthToken.objects.create(user=self.user)
        self.assertTrue(token.last_used_on is None)

    def test_lookup_user_for_secret_returns_none_on_failure(self):
        user = AuthToken.get_user_for_secret(
            self.user.username, self._INEXISTING_SECRET)
        self.assertTrue(user is None)

    def test_get_user_for_secret_finds_valid_user(self):
        token = AuthToken.objects.create(user=self.user)
        user = AuthToken.get_user_for_secret(self.user.username, token.secret)
        self.assertEqual(user, self.user)

    def test_get_user_for_secret_checks_if_the_user_matches(self):
        token = AuthToken.objects.create(user=self.user)
        user = AuthToken.get_user_for_secret(
            self._INEXISTING_USER, token.secret)
        self.assertEqual(user, None)

    def test_get_user_for_secret_sets_last_used_on(self):
        token = AuthToken.objects.create(user=self.user)
        AuthToken.get_user_for_secret(self.user.username, token.secret)
        # Refresh token
        token = AuthToken.objects.get(user=self.user)
        self.assertNotEqual(token.last_used_on, None)
