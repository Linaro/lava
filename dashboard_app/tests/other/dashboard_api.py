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
Unit tests for Dashboard API (XML-RPC interface)
"""
import contextlib
import xmlrpclib

from django.core.urlresolvers import reverse
from django_testscenarios import TransactionTestCase

from dashboard_app.models import Bundle
from dashboard_app.tests import fixtures
from dashboard_app.tests.utils import DashboardXMLRPCViewsTestCase
from dashboard_app.xmlrpc import errors


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
                ".".join(map(str, __version__.as_tuple)))


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
        super(DashboardAPIPutFailureTransactionTests, self).setUp()
        self.endpoint_path = reverse("dashboard_app.dashboard_xml_rpc_handler")

    def tearDown(self):
        super(DashboardAPIPutFailureTransactionTests, self).tearDown()
        Bundle.objects.all().delete()

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
