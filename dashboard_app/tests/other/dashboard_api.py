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
from django_testscenarios.ubertest import TransactionTestCase

from dashboard_app.models import Bundle, BundleStream
from dashboard_app.tests import fixtures
from dashboard_app.tests.utils import DashboardXMLRPCViewsTestCase
from dashboard_app.xmlrpc import errors


class DashboardAPIStreamsTests(DashboardXMLRPCViewsTestCase):

    scenarios = [
        ('empty', {
            'pathnames': [],
            'expected_response': [],
        }),
        ('anonymous_stream', {
            'pathnames': [
                '/anonymous/',
            ],
            'expected_response': [{
                'bundle_count': 0,
                'user': 'anonymous-stream-owner',
                'group': '',
                'name': '',
                'pathname': '/anonymous/'}],
        }),
        ('public_streams_are_shown', {
            'pathnames': [
                '/public/personal/user/',
                '/public/team/group/',
            ],
            'expected_response': [{
                'bundle_count': 0,
                'user': 'user',
                'group': '',
                'name': '',
                'pathname': '/public/personal/user/',
            }, {
                'bundle_count': 0,
                'user': '',
                'group': 'group',
                'name': '',
                'pathname': '/public/team/group/',
            }],
        }),
        ('private_streams_are_not_shown', {
            'pathnames': [
                '/private/personal/user/',
                '/private/team/group/',
            ],
            'expected_response': [],
        }),
    ]

    def test_streams(self):
        """
        Check that calling streams() returns all the registered
        streams visible to anonymous user.
        """
        with fixtures.created_bundle_streams(self.pathnames):
            response = self.xml_rpc_call('streams')
            self.assertEqual(response, self.expected_response)


class DashboardAPIBundlesTests(DashboardXMLRPCViewsTestCase):

    scenarios = [
        ('empty', {
            'query': '/anonymous/',
            # make one anonymous stream so that we don't get 404 accessing missing one
            'bundle_streams': ['/anonymous/'],
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
            fixtures.created_bundles(self.bundles)
        ):
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
        }),
        ('no_anonymous_access_to_private_personal_streams', {
            'bundle_streams': [
                '/private/personal/user/',
            ],
            'query': '/private/personal/user/',
        }),
        ('no_anonymous_access_to_private_team_streams', {
            'bundle_streams': [
                '/private/team/group/',
            ],
            'query': '/private/team/group/',
        }),
    ]

    def test_bundles_failure(self):
        with fixtures.created_bundle_streams(self.bundle_streams):
            try:
                self.xml_rpc_call("bundles", self.query)
            except xmlrpclib.Fault as ex:
                self.assertEqual(ex.faultCode, errors.NOT_FOUND)
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
        }),
        ('no_access_to_personal_bundles', {
            'bundles': [
                ('/private/personal/bob/', 'test1.json', '{"foobar": 5}'),
            ],
        }),
        ('no_access_to_named_personal_bundles', {
            'bundles': [
                ('/private/personal/bob/some-name/', 'test1.json', '{"foobar": 5}'),
            ],
        }),
        ('no_access_to_team_bundles', {
            'bundles': [
                ('/private/team/members/', 'test1.json', '{"foobar": 5}'),
            ],
        }),
        ('no_access_to_named_team_bundles', {
            'bundles': [
                ('/private/team/members/some-name/', 'test1.json', '{"foobar": 5}'),
            ],
        }),
    ]

    bundles = []
    # SHA1 of the content used in scenarios above
    content_sha1='72996acd68de60c766b60c2ca6f6169f67cdde19'

    def test_get_failure(self):
        with fixtures.created_bundles(self.bundles):
            try:
                self.xml_rpc_call('get', self.content_sha1)
            except xmlrpclib.Fault as ex:
                self.assertEqual(ex.faultCode, errors.NOT_FOUND)
            else:
                self.fail("Should have raised an exception")


class DashboardAPIPutTests(DashboardXMLRPCViewsTestCase):

    scenarios = [
        ('store_to_public_stream', {
            'content': '{"foobar": 5}',
            'content_filename': 'test1.json',
            'pathname': '/anonymous/',
        }),
        ('store_to_public_named_stream', {
            'content': '{"foobar": 5}',
            'content_filename': 'test1.json',
            'pathname': '/anonymous/some-name/',
        }),
    ]

    def setUp(self):
        super(DashboardAPIPutTests, self).setUp()
        self.bundle_stream = fixtures.create_bundle_stream(self.pathname)
        self.bundle = None

    def tearDown(self):
        if self.bundle:
            self.bundle.delete_files()
        super(DashboardAPIPutTests, self).tearDown()

    def test_put(self):
        content_sha1 = self.xml_rpc_call(
            "put", self.content, self.content_filename, self.pathname)
        self.bundle = Bundle.objects.get(content_sha1=content_sha1)
        self.assertEqual(self.bundle.content_sha1, content_sha1)
        self.assertEqual(self.bundle.content.read(), self.content)
        self.assertEqual(self.bundle.content_filename, self.content_filename)
        self.assertEqual(self.bundle.bundle_stream.pathname, self.pathname)


class DashboardAPIPutFailureTests(DashboardXMLRPCViewsTestCase):
   
    scenarios = [
        ('store_to_personal_stream', {
            'content': '{"foobar": 5}',
            'content_filename': 'test1.json',
            'pathname': '/private/personal/user/',
            'faultCode': errors.NOT_FOUND,
            }),
        ('store_to_named_personal_stream', {
            'content': '{"foobar": 5}',
            'content_filename': 'test1.json',
            'pathname': '/private/personal/user/name/',
            'faultCode': errors.NOT_FOUND,
            }),
        ('store_to_team_stream', {
            'content': '{"foobar": 5}',
            'content_filename': 'test1.json',
            'pathname': '/private/team/group/',
            'faultCode': errors.NOT_FOUND,
            }),
        ('store_to_named_team_stream', {
            'content': '{"foobar": 5}',
            'content_filename': 'test1.json',
            'pathname': '/private/team/group/name/',
            'faultCode': errors.NOT_FOUND,
            }),
        ('store_to_missing_stream', {
            'content': '{"foobar": 5}',
            'content_filename': 'test1.json',
            'pathname': '/anonymous/',
            'faultCode': errors.NOT_FOUND,
            'do_not_create': True,
            }),
        ]

    def test_put_failure(self):
        with contextlib.nested(
            fixtures.created_bundle_streams(
                [] if getattr(self, 'do_not_create', False) else [self.pathname]),
            fixtures.created_bundles(getattr(self, 'bundles', []))
        ):
            try:
                self.xml_rpc_call(
                    "put", self.content, self.content_filename, self.pathname)
            except xmlrpclib.Fault as ex:
                self.assertEqual(ex.faultCode, self.faultCode)
            else:
                self.fail("Should have raised an exception")


class DashboardAPIPutFailureTransactionTests(TransactionTestCase):

    def setUp(self):
        super(DashboardAPIPutFailureTransactionTests, self).setUp()
        self.endpoint_path = reverse(
            "dashboard_app.views.dashboard_xml_rpc_handler")
        self.content_sha1 = None

    def tearDown(self):
        if self.content_sha1:
            Bundle.objects.get(content_sha1=self.content_sha1).delete_files()
        super(DashboardAPIPutFailureTransactionTests, self).tearDown()

    def xml_rpc_call(self, method, *args):
        request_body = xmlrpclib.dumps(tuple(args), methodname=method)
        response = self.client.post(self.endpoint_path,
                request_body, "text/xml")
        return xmlrpclib.loads(response.content)[0][0]

    def test_deserialize_failure_does_not_kill_the_bundle(self):
        _pathname = '/anonymous/'
        _content = '"unterminated string'
        _content_filename = 'bad.json'
        # The test goes via the xml-rpc interface to use views calling the
        # put() API directly will never trigger transactions handling
        with fixtures.created_bundle_streams([_pathname]):
            self.content_sha1 = self.xml_rpc_call(
                "put", _content, _content_filename, _pathname)
            self.assertEqual(Bundle.objects.all().count(), 1)

    def test_put_duplicate(self):
        _bundles = [('/anonymous/', 'test1.json', '{"foobar": 5}')]
        _content = '{"foobar": 5}'
        _content_filename = 'test1.json'
        _pathname = '/anonymous/'
        with fixtures.created_bundles(_bundles):
            try:
                self.content_sha1 = self.xml_rpc_call(
                    "put", _content, _content_filename, _pathname)
            except xmlrpclib.Fault as ex:
                self.assertEqual(ex.faultCode, errors.CONFLICT)
            else:
                self.fail("Should have raised an exception")


class DashboardAPIMakeStreamTests(DashboardXMLRPCViewsTestCase):

    scenarios = [
        ('toplevel_anonymous/', {
            'pathname': '/anonymous/',
            'name': '',
        }),
        ('anonymous_with_slug', {
            'pathname': '/anonymous/some-name/',
            'name': '',
        }),
        ('anonymous_with_slug_and_name', {
            'pathname': '/anonymous/some-name/',
            'name': 'nonempty',
        }),
    ]

    def setUp(self):
        super(DashboardAPIMakeStreamTests, self).setUp()
        self.response = self.xml_rpc_call("make_stream", self.pathname, self.name)

    def test_response_is_pathname(self):
        self.assertEqual(self.response, self.pathname)

    def test_pathname_is_created(self):
        self.assertEqual(BundleStream.objects.filter(pathname=self.pathname).count(), 1)

    def test_pathname_has_name(self):
        bundle_stream = BundleStream.objects.get(pathname=self.pathname)
        self.assertEqual(self.name, bundle_stream.name)


class DashboardAPIMakeStreamFailureTests(DashboardXMLRPCViewsTestCase):

    _NAME = ""

    scenarios = [
        ('public_personal', {
            'pathname': '/public/personal/NAME/',
        }),
        ('private_personal', {
            'pathname': '/private/personal/NAME/',
        }),
        ('public_team', {
            'pathname': '/public/team/NAME/',
        }),
        ('private_team', {
            'pathname': '/private/team/NAME/',
        }),
        ('public_personal_with_slug', {
            'pathname': '/public/personal/NAME/SLUG/',
        }),
        ('private_personal_with_slug', {
            'pathname': '/private/personal/NAME/SLUG/',
        }),
        ('public_team_with_slug', {
            'pathname': '/public/team/NAME/SLUG/',
        }),
        ('private_team_with_slug', {
            'pathname': '/private/team/NAME/SLUG/',
        }),
        ('bogus', {
            'pathname': '/bogus/pathname/'
        }),
    ]

    def test_nonanonymous_streams(self):
        try:
            self.xml_rpc_call("make_stream", self.pathname, self._NAME)
        except xmlrpclib.Fault as ex:
            self.assertEqual(ex.faultCode, errors.FORBIDDEN)
        else:
            self.fail("Should have raised an exception")
