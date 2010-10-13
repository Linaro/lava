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
Unit tests of the Dashboard application
"""
import contextlib
import datetime
import decimal
import hashlib
import os
import uuid
import xmlrpclib

from django.conf import settings
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes import generic
from django.core.files.base import ContentFile
from django.core.urlresolvers import reverse, resolve
from django.db import models, IntegrityError
from django.test import TestCase, TransactionTestCase

from dashboard_app.tests import fixtures
from dashboard_app.tests.utils import TestClient
from dashboard_app.models import (
        Attachment,
        Bundle,
        BundleDeserializationError,
        BundleStream,
        HardwareDevice,
        NamedAttribute,
        SoftwarePackage,
        Test,
        TestCase as TestCaseModel,
        TestResult,
        TestRun,
        )
from dashboard_app.helpers import (
        BundleDeserializer,
        DocumentError,
        )
from dashboard_app.dispatcher import (
        DjangoXMLRPCDispatcher,
        FaultCodes,
        xml_rpc_signature,
        )
from dashboard_app.xmlrpc import errors
from launch_control.thirdparty.mocker import Mocker, expect
from launch_control.utils.call_helper import ObjectFactoryMixIn
from launch_control import models as client_models


class TestAPI(object):
    """
    Test API that gets exposed by the dispatcher for test runs.
    """

    @xml_rpc_signature()
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


class DjangoXMLRPCDispatcherTestCase(TestCase):

    def setUp(self):
        super(DjangoXMLRPCDispatcherTestCase, self).setUp()
        self.dispatcher = DjangoXMLRPCDispatcher()
        self.dispatcher.register_instance(TestAPI())

    def xml_rpc_call(self, method, *args):
        """
        Perform XML-RPC call on our internal dispatcher instance

        This calls the method just like we would have normally from our view.
        All arguments are marshaled and un-marshaled. XML-RPC fault exceptions
        are raised like normal python exceptions (by xmlrpclib.loads)
        """
        request = xmlrpclib.dumps(tuple(args), methodname=method)
        response = self.dispatcher._marshaled_dispatch(request)
        # This returns return value wrapped in a tuple and method name
        # (which we don't have here as this is a response message).
        return xmlrpclib.loads(response)[0][0]


class DjangoXMLRPCDispatcherTests(DjangoXMLRPCDispatcherTestCase):

    def test_standard_fault_code_for_missing_method(self):
        try:
            self.xml_rpc_call("method_that_hopefully_does_not_exist")
        except xmlrpclib.Fault as ex:
            self.assertEqual(
                    ex.faultCode,
                    FaultCodes.ServerError.REQUESTED_METHOD_NOT_FOUND)
        else:
            self.fail("Calling missing method did not raise an exception")

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


class DjangoXMLRPCDispatcherFaultCodeTests(DjangoXMLRPCDispatcherTestCase):

    scenarios = [
            ('method_not_found', {
                'method': "method_that_hopefully_does_not_exist",
                'faultCode': FaultCodes.ServerError.REQUESTED_METHOD_NOT_FOUND,
                }),
            ('internal_error', {
                'method': "internal_boom",
                'faultCode': FaultCodes.ServerError.INTERNAL_XML_RPC_ERROR,
                }),
            ]

    def test_standard_fault_codes(self):
        try:
            self.xml_rpc_call(self.method)
        except xmlrpclib.Fault as ex:
            self.assertEqual(ex.faultCode, self.faultCode)
        else:
            self.fail("Exception not raised")


class DashboardViewsTestCase(TestCase):
    """
    Helper class that ensures dashboard views are mapped in URLs the way
    we expect, regardless of actual deployment.
    """
    urls = 'dashboard_app.urls'

    def setUp(self):
        super(DashboardViewsTestCase, self).setUp()
        self.old_LANGUAGES = settings.LANGUAGES
        self.old_LANGUAGE_CODE = settings.LANGUAGE_CODE
        settings.LANGUAGES = (('en', 'English'),)
        settings.LANGUAGE_CODE = 'en'
        self.old_TEMPLATE_DIRS = settings.TEMPLATE_DIRS
        settings.TEMPLATE_DIRS = (
            os.path.join(
                os.path.dirname(__file__),
                'templates'
            )
        ,)

    def tearDown(self):
        settings.LANGUAGES = self.old_LANGUAGES
        settings.LANGUAGE_CODE = self.old_LANGUAGE_CODE
        settings.TEMPLATE_DIRS = self.old_TEMPLATE_DIRS
        super(DashboardViewsTestCase, self).tearDown()


class DashboardXMLRPCViewsTestCase(DashboardViewsTestCase):
    """
    Helper base class for doing XML-RPC requests
    """

    def setUp(self):
        super(DashboardXMLRPCViewsTestCase, self).setUp()
        self.endpoint_path = reverse("dashboard_app.dashboard_xml_rpc_handler")

    def xml_rpc_call(self, method, *args):
        request_body = xmlrpclib.dumps(tuple(args), methodname=method)
        response = self.client.post(self.endpoint_path,
                request_body, "text/xml")
        return xmlrpclib.loads(response.content)[0][0]


class TestClientTest(TestCase):

    _USER = "user"

    urls = 'dashboard_app.tests.urls'

    def setUp(self):
        super(TestClientTest, self).setUp()
        self.client = TestClient()
        self.user = User(username=self._USER)
        self.user.save()

    def test_auth(self):
        self.client.login_user(self.user)
        response = self.client.get("/auth-test/")
        self.assertEqual(response.content, self._USER)

    def test_no_auth(self):
        response = self.client.get("/auth-test/")
        self.assertEqual(response.content, '')


class DashboardAPITests(DashboardXMLRPCViewsTestCase):

    def test_xml_rpc_help_returns_200(self):
        response = self.client.get("/xml-rpc/")
        self.assertEqual(response.status_code, 200)

    def test_help_page_lists_all_methods(self):
        from dashboard_app.views import DashboardDispatcher as dispatcher
        expected_methods = []
        for name in dispatcher.system_listMethods():
            expected_methods.append({
                'name': name,
                'signature': dispatcher.system_methodSignature(name),
                'help': dispatcher.system_methodHelp(name)
                })
        response = self.client.get("/xml-rpc/")
        self.assertEqual(response.context['methods'], expected_methods)

    def test_get_request_shows_help(self):
        response = self.client.get("/xml-rpc/")
        self.assertTemplateUsed(response, "dashboard_app/api.html")

    def test_empty_post_request_shows_help(self):
        response = self.client.post("/xml-rpc/")
        self.assertTemplateUsed(response, "dashboard_app/api.html")

    def test_version(self):
        from dashboard_app import __version__
        self.assertEqual(self.xml_rpc_call('version'),
                ".".join(map(str, __version__)))


class DashboardAPIStreamsTests(DashboardXMLRPCViewsTestCase):

    scenarios = [
        ('empty', {
            'streams': [],
            'expected_response': [],
            }),
        ('one_public_stream', {
            'streams': [
                {'slug': '', 'user': None, 'group': None}],
            'expected_response': [{
                'bundle_count': 0,
                'user': '',
                'group': '',
                'name': '',
                'pathname': '/anonymous/'}],
            }),
        ('private_streams_are_not_shown', {
            'streams': [
                {'slug': '', 'user': 'joe', 'group': None},
                {'slug': '', 'user': None, 'group': None}],
            'expected_response': [{
                'bundle_count': 0,
                'user': '',
                'group': '',
                'name': '',
                'pathname': '/anonymous/'}],
            }),
        ('team_streams_are_not_shown', {
            'streams': [
                {'slug': '', 'user': None, 'group': 'group'},
                {'slug': '', 'user': None, 'group': None}],
            'expected_response': [{
                'bundle_count': 0,
                'user': '',
                'group': '',
                'name': '',
                'pathname': '/anonymous/'}],
            }),
        ]

    def test_streams(self):
        with fixtures.created_bundle_streams(self.streams):
            response = self.xml_rpc_call('streams')
            self.assertEqual(response, self.expected_response)


class DashboardAPIBundlesTests(DashboardXMLRPCViewsTestCase):

    scenarios = [
        ('empty', {
            'query': '/anonymous/',
            'bundle_streams': [{}], # make one anonymous stream so that we don't get 404 accessing missing one
            'bundles': [],
            'expected_results': [],
            }),
        ('several_bundles_we_can_see', {
            'query': '/anonymous/',
            'bundle_streams': [],
            'bundles': [
                ('/anonymous/', 'test1.json', '{"foobar": 5}'),
                ('/anonymous/', 'test2.json', '{"froz": "bot"}'),
                ],
            'expected_results': [{
                'content_filename': 'test1.json',
                'content_sha1': '72996acd68de60c766b60c2ca6f6169f67cdde19',
                }, {
                'content_filename': 'test2.json',
                'content_sha1': '67dd49730d4e3b38b840f3d544d45cad74bcfb09',
                }],
            }),
        ('several_bundles_in_other_stream', {
            'query': '/anonymous/other/',
            'bundle_streams': [],
            'bundles': [
                ('/anonymous/', 'test3.json', '{}'),
                ('/anonymous/other/', 'test4.json', '{"x": true}'),
                ],
            'expected_results': [{
                'content_filename': 'test4.json',
                'content_sha1': 'bac148f29c35811441a7b4746a022b04c65bffc0',
                }],
            }),
        ]

    def test_bundles(self):
        """
        Make a bunch of bundles (all in a public branch) and check that
        they are returned by the XML-RPC request.
        """
        with contextlib.nested(
                fixtures.created_bundle_streams(self.bundle_streams),
                fixtures.created_bundles(self.bundles)):
            results = self.xml_rpc_call('bundles', self.query)
            self.assertEqual(len(results), len(self.expected_results))
            with fixtures.test_loop(zip(results, self.expected_results)) as loop_items:
                for result, expected_result in loop_items:
                    self.assertEqual(
                            result['content_filename'],
                            expected_result['content_filename'])
                    self.assertEqual(
                            result['content_sha1'],
                            expected_result['content_sha1'])


class DashboardAPIBundlesFailureTests(DashboardXMLRPCViewsTestCase):

    scenarios = [
        ('no_such_stream', {
            'bundle_streams': [],
            'query': '/anonymous/',
            'expected_faultCode': errors.NOT_FOUND,
            }),
        ('no_anonymous_access_to_personal_streams', {
            'bundle_streams': [{'user': 'user'}],
            'query': '/personal/user/',
            'expected_faultCode': errors.FORBIDDEN,
            }),
        ('no_anonymous_access_to_team_streams', {
            'bundle_streams': [{'group': 'group'}],
            'query': '/team/group/',
            'expected_faultCode': errors.FORBIDDEN,
            }),
        ]

    def test_bundles_failure(self):
        with fixtures.created_bundle_streams(self.bundle_streams):
            try:
                self.xml_rpc_call("bundles", self.query)
            except xmlrpclib.Fault as ex:
                self.assertEqual(ex.faultCode, self.expected_faultCode)
            else:
                self.fail("Should have raised an exception")


class DashboardAPIGetTests(DashboardXMLRPCViewsTestCase):

    scenarios = [
        ('bundle_we_can_access', {
            'content_sha1': '72996acd68de60c766b60c2ca6f6169f67cdde19',
            'bundles': [
                ('/anonymous/', 'test1.json', '{"foobar": 5}'),
                ('/anonymous/', 'test2.json', '{"froz": "bot"}'),
                ],
            'expected_result': {
                'content_filename': 'test1.json',
                'content': '{"foobar": 5}',
                }
            }),
        ]

    def test_get(self):
        """
        Make a bunch of bundles (all in a public branch) and check that
        we can get them back by calling get()
        """
        with fixtures.created_bundles(self.bundles):
            result = self.xml_rpc_call('get', self.content_sha1)
            self.assertTrue(isinstance(result, dict))
            self.assertEqual(
                    result['content_filename'],
                    self.expected_result['content_filename'])
            self.assertEqual(
                    result['content'],
                    self.expected_result['content'])


class DashboardAPIGetFailureTests(DashboardXMLRPCViewsTestCase):

    scenarios = [
        ('bad_sha1', {
            'content_sha1': '',
            'faultCode': errors.NOT_FOUND
            }),
        ('no_access_to_personal_bundles', {
            'bundles': [
                ('/personal/bob/', 'test1.json', '{"foobar": 5}'),
                ],
            'faultCode': errors.FORBIDDEN
            }),
        ('no_access_to_named_personal_bundles', {
            'bundles': [
                ('/personal/bob/some-name/', 'test1.json', '{"foobar": 5}'),
                ],
            'faultCode': errors.FORBIDDEN
            }),
        ('no_access_to_team_bundles', {
            'bundles': [
                ('/team/members/', 'test1.json', '{"foobar": 5}'),
                ],
            'faultCode': errors.FORBIDDEN
            }),
        ('no_access_to_named_team_bundles', {
            'bundles': [
                ('/team/members/some-name/', 'test1.json', '{"foobar": 5}'),
                ],
            'faultCode': errors.FORBIDDEN
            }),
        ]

    bundles = []
    content_sha1='72996acd68de60c766b60c2ca6f6169f67cdde19'

    def test_get_failure(self):
        with fixtures.created_bundles(self.bundles):
            try:
                self.xml_rpc_call('get', self.content_sha1)
            except xmlrpclib.Fault as ex:
                self.assertEqual(ex.faultCode, self.faultCode)
            else:
                self.fail("Should have raised an exception")


class DashboardAPIPutTests(DashboardXMLRPCViewsTestCase):

    scenarios = [
        ('store_to_public_stream', {
            'bundle_streams': [{}],
            'content': '{"foobar": 5}',
            'content_filename': 'test1.json',
            'pathname': '/anonymous/',
            }),
        ('store_to_public_named_stream', {
            'bundle_streams': [{'slug': 'some-name'}],
            'content': '{"foobar": 5}',
            'content_filename': 'test1.json',
            'pathname': '/anonymous/some-name/',
            }),
        ]

    def test_put(self):
        with fixtures.created_bundle_streams(self.bundle_streams):
            content_sha1 = self.xml_rpc_call("put",
                    self.content, self.content_filename, self.pathname)
            stored = Bundle.objects.get(content_sha1=content_sha1)
            try:
                self.assertEqual(stored.content_sha1, content_sha1)
                self.assertEqual(stored.content.read(), self.content)
                self.assertEqual(
                    stored.content_filename, self.content_filename)
                self.assertEqual(stored.bundle_stream.pathname, self.pathname)
            finally:
                stored.delete()


class DashboardAPIPutFailureTests(DashboardXMLRPCViewsTestCase):

    scenarios = [
        ('store_to_personal_stream', {
            'bundle_streams': [{'user': 'joe'}],
            'content': '{"foobar": 5}',
            'content_filename': 'test1.json',
            'pathname': '/personal/joe/',
            'faultCode': errors.FORBIDDEN,
            }),
        ('store_to_named_personal_stream', {
            'bundle_streams': [{'user': 'joe', 'slug': 'some-name'}],
            'content': '{"foobar": 5}',
            'content_filename': 'test1.json',
            'pathname': '/personal/joe/some-name/',
            'faultCode': errors.FORBIDDEN,
            }),
        ('store_to_team_stream', {
            'bundle_streams': [{'group': 'members'}],
            'content': '{"foobar": 5}',
            'content_filename': 'test1.json',
            'pathname': '/team/members/',
            'faultCode': errors.FORBIDDEN,
            }),
        ('store_to_named_team_stream', {
            'bundle_streams': [{'group': 'members', 'slug': 'some-name'}],
            'content': '{"foobar": 5}',
            'content_filename': 'test1.json',
            'pathname': '/team/members/some-name/',
            'faultCode': errors.FORBIDDEN,
            }),
        ('store_to_missing_stream', {
            'bundle_streams': [],
            'content': '{"foobar": 5}',
            'content_filename': 'test1.json',
            'pathname': '/anonymous/',
            'faultCode': errors.NOT_FOUND,
            }),
        ('store_duplicate', {
            'bundle_streams': [],
            'bundles': [('/anonymous/', 'test1.json', '{"foobar": 5}')],
            'content': '{"foobar": 5}',
            'content_filename': 'test1.json',
            'pathname': '/anonymous/',
            'faultCode': errors.CONFLICT,
            }),
        ]

    bundles = []

    def test_put_failure(self):
        with contextlib.nested(
                fixtures.created_bundle_streams(self.bundle_streams),
                fixtures.created_bundles(self.bundles)):
            try:
                self.xml_rpc_call("put", self.content, self.content_filename,
                        self.pathname)
            except xmlrpclib.Fault as ex:
                self.assertEqual(ex.faultCode, self.faultCode)
            else:
                self.fail("Should have raised an exception")


class DashboardAPIPutFailureTransactionTests(TransactionTestCase):

    _bundle_streams = [{}]
    _content = '"unterminated string'
    _content_filename = 'bad.json'
    _pathname =  '/anonymous/'

    def setUp(self):
        self.endpoint_path = reverse("dashboard_app.dashboard_xml_rpc_handler")

    def xml_rpc_call(self, method, *args):
        request_body = xmlrpclib.dumps(tuple(args), methodname=method)
        response = self.client.post(self.endpoint_path,
                request_body, "text/xml")
        return xmlrpclib.loads(response.content)[0][0]

    def test_deserialize_failure_does_not_kill_the_bundle(self):
        # The test goes via the xml-rpc interface to use views
        # calling the put() API directly will never trigger out
        # transactions
        with fixtures.created_bundle_streams(self._bundle_streams):
            self.xml_rpc_call("put", self._content, self._content_filename,
                    self._pathname)
            self.assertEqual(Bundle.objects.all().count(), 1)


class DjangoTestCaseWithScenarios(TestCase):

    scenarios = [
            ('a', {}),
            ('b', {}),
            ]

    def test_database_is_empty_at_start_of_test(self):
        self.assertEqual(BundleStream.objects.all().count(), 0)
        stream = BundleStream.objects.create(slug='')


class BundleStreamListViewAnonymousTest(DashboardViewsTestCase):

    _USER = "user"
    _GROUP = "group"
    _SLUG = "slug"

    scenarios = [
        ('empty', {
            'bundle_streams': [],
        }),
        ('public_streams', {
            'bundle_streams': [
                {'slug': ''},
                {'slug': _SLUG},],
        }),
        ('private_streams', {
            'bundle_streams': [
                {'slug': '', 'user': _USER},
                {'slug': _SLUG, 'user': _USER},],
        }),
        ('team_streams', {
            'bundle_streams': [
                {'slug': '', 'group': _GROUP},
                {'slug': _SLUG, 'group': _GROUP},],
        }),
        ('various_streams', {
            'bundle_streams': [
                {'slug': ''},
                {'slug': _SLUG},
                {'slug': '', 'user': _USER},
                {'slug': _SLUG, 'user': _USER},
                {'slug': '', 'group': _GROUP},
                {'slug': _SLUG, 'group': _GROUP},
            ],
        }),
    ]

    def setUp(self):
        super(BundleStreamListViewAnonymousTest, self).setUp()
        self.user = None

    def test_status_code(self):
        response = self.client.get("/streams/")
        self.assertEqual(response.status_code, 200)

    def test_template_used(self):
        response = self.client.get("/streams/")
        self.assertTemplateUsed(response,
                "dashboard_app/bundle_stream_list.html")

    def test_listed_bundles_are_the_ones_we_should_see(self):
        with fixtures.created_bundle_streams(self.bundle_streams) as bundle_streams:
            response = self.client.get("/streams/")
            expected_bsl = sorted(
                    [bundle_stream.pk for bundle_stream in
                        bundle_streams if
                        bundle_stream.can_access(self.user)])
            effective_bsl = sorted(
                    [bundle_stream.pk for bundle_stream in
                        response.context['bundle_stream_list']])
            self.assertEqual(effective_bsl, expected_bsl)


class BundleStreamListViewAuthorizedTest(BundleStreamListViewAnonymousTest):

    def setUp(self):
        super(BundleStreamListViewAuthorizedTest, self).setUp()
        self.client = TestClient()
        self.user = User.objects.create(username=self._USER)
        self.user.groups.create(name=self._GROUP)
        self.client.login_user(self.user)


class BundleStreamDetailViewAnonymousTest(DashboardViewsTestCase):

    _USER = "user"
    _GROUP = "group"
    _SLUG = "slug"

    scenarios = [
        ('public_stream', {'slug': ''}),
        ('public_named_stream', {'slug': _SLUG}),
        ('private_stream', {'slug': '', 'user': _USER}),
        ('private_named_stream', {'slug': _SLUG, 'user': _USER}),
        ('team_stream', {'slug': '', 'group': _GROUP}),
        ('team_named_stream', {'slug': _SLUG, 'group': _GROUP})
    ]

    def setUp(self):
        super(BundleStreamDetailViewAnonymousTest, self).setUp()
        self.bundle_stream = fixtures.make_bundle_stream(dict(
            slug=self.slug,
            user=getattr(self, 'user', ''),
            group=getattr(self, 'group', '')))
        self.user = None

    def test_status_code(self):
        response = self.client.get("/streams" + self.bundle_stream.pathname)
        if self.bundle_stream.can_access(self.user):
            self.assertEqual(response.status_code, 200)
        else:
            self.assertEqual(response.status_code, 403)

    def test_template_used(self):
        response = self.client.get("/streams" + self.bundle_stream.pathname)
        if self.bundle_stream.can_access(self.user):
            self.assertTemplateUsed(response,
                "dashboard_app/bundle_stream_detail.html")
        else:
            self.assertTemplateUsed(response,
                "403.html")


class BundleStreamDetailViewAuthorizedTest(BundleStreamDetailViewAnonymousTest):

    def setUp(self):
        super(BundleStreamDetailViewAuthorizedTest, self).setUp()
        self.client = TestClient()
        self.user = User.objects.get_or_create(username=self._USER)[0]
        self.group = Group.objects.get_or_create(name=self._GROUP)[0]
        self.user.groups.add(self.group)
        self.client.login_user(self.user)


class TestUnicodeMethods(TestCase):

    def test_bundle_deserialization_error(self):
        obj = BundleDeserializationError(error_message="boom")
        self.assertEqual(unicode(obj), u"boom")
