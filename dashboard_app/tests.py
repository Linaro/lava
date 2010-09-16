"""
Unit tests of the Dashboard application
"""
import contextlib
import datetime
import hashlib
import xmlrpclib

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes import generic
from django.core.files.base import ContentFile
from django.db import models, IntegrityError
from django.http import HttpRequest
from django.test import TestCase
from django.test.client import Client
from django.utils.importlib import import_module

from dashboard_app import fixtures
from dashboard_app.models import (
        Bundle,
        BundleDeserializationError,
        BundleStream,
        HardwareDevice,
        SoftwarePackage,
        Test,
        TestCase as TestCaseModel,
        TestResult,
        TestRun,
        Attachment,
        )
from dashboard_app.dispatcher import (
        DjangoXMLRPCDispatcher,
        FaultCodes,
        xml_rpc_signature,
        )
from dashboard_app.xmlrpc import errors
from launch_control.thirdparty.mocker import Mocker, expect
from launch_control.utils.call_helper import ObjectFactoryMixIn


class SoftwarePackageTestCase(TestCase, ObjectFactoryMixIn):

    class Dummy:
        class SoftwarePackage:
            name = 'libfoo'
            version = '1.2.0'

    def test_creation_1(self):
        dummy, sw_package = self.make_and_get_dummy(SoftwarePackage)
        sw_package.save()
        self.assertEqual(sw_package.name, dummy.name)
        self.assertEqual(sw_package.version, dummy.version)

    def test_uniqueness(self):
        pkg1 = self.make(SoftwarePackage)
        pkg1.save()
        pkg2 = self.make(SoftwarePackage)
        self.assertRaises(IntegrityError, pkg2.save)


class HardwarePackageTestCase(TestCase, ObjectFactoryMixIn):

    class Dummy:
        class HardwareDevice:
            device_type = 'device.cpu'
            description = 'some cpu'

    def test_creation(self):
        dummy, hw_device = self.make_and_get_dummy(HardwareDevice)
        hw_device.save()
        self.assertEqual(hw_device.device_type, dummy.device_type)
        self.assertEqual(hw_device.description, dummy.description)

    def test_attributes(self):
        hw_device = self.make(HardwareDevice)
        hw_device.save()
        hw_device.attributes.create(name="connection-bus", value="usb")
        self.assertEqual(hw_device.attributes.count(), 1)
        attr = hw_device.attributes.get()
        self.assertEqual(attr.name, "connection-bus")
        self.assertEqual(attr.value, "usb")

    def test_attributes_uniqueness(self):
        hw_device = self.make(HardwareDevice)
        hw_device.save()
        hw_device.attributes.create(name="name", value="value")
        self.assertRaises(IntegrityError, hw_device.attributes.create,
                name="name", value="value")


class BundleTest(TestCase):

    _NAME = "name"
    _SLUG = "slug"
    _GROUPNAME = "group"
    _USERNAME = "user"

    scenarios = [
        ('anonymous-no-slug', {
            'pathname': '/anonymous/',
            }),
        ('anonymous-with-slug', {
            'name': _NAME,
            'slug': _SLUG,
            'pathname': '/anonymous/slug/',
            }),
        ('personal-no-slug', {
            'username': _USERNAME,
            'pathname': '/personal/user/',
            }),
        ('personal-with-slug', {
            'username': _USERNAME,
            'name': _NAME,
            'slug': _SLUG,
            'pathname': '/personal/user/slug/',
            }),
        ('team-no-slug', {
            'groupname': _GROUPNAME,
            'pathname': '/team/group/',
            }),
        ('team-with-slug', {
            'groupname': _GROUPNAME,
            'name': _NAME,
            'slug': _SLUG,
            'pathname': '/team/group/slug/',
            }),
        ]

    groupname = None
    username = None
    group = None
    user = None
    name = ''
    slug = ''

    def setUp(self):
        super(BundleTest, self).setUp()
        if self.username is not None:
            self.user = User.objects.create(username='user')
        if self.groupname is not None:
            self.group = Group.objects.create(name='group')

    def test_creation(self):
        bundle_stream = BundleStream.objects.create(user=self.user,
                group=self.group, name=self.name, slug=self.slug)
        bundle_stream.save()
        self.assertEqual(bundle_stream.user, self.user)
        self.assertEqual(bundle_stream.group, self.group)
        self.assertEqual(bundle_stream.name, self.name)
        self.assertEqual(bundle_stream.slug, self.slug)

    def test_team_named_stream(self):
        bundle_stream = BundleStream.objects.create(user=self.user,
                group=self.group, name=self.name, slug=self.slug)
        bundle_stream.save()
        self.assertEqual(bundle_stream.pathname, self.pathname)

    def test_pathname_uniqueness(self):
        bundle_stream = BundleStream.objects.create(user=self.user,
                group=self.group, name=self.name, slug=self.slug)
        bundle_stream.save()
        self.assertRaises(IntegrityError,
                BundleStream.objects.create,
                user=self.user, group=self.group, slug=self.slug,
                name=self.name)

    def test_pathname_update(self):
        bundle_stream = BundleStream.objects.create(user=self.user,
                group=self.group, name=self.name, slug=self.slug)
        bundle_stream.save()
        old_pathname = bundle_stream.pathname
        bundle_stream.slug += "-changed"
        bundle_stream.save()
        self.assertNotEqual(bundle_stream.pathname, old_pathname)
        self.assertEqual(bundle_stream.pathname,
                bundle_stream._calc_pathname())


class BundleDeserializationTestCase(TestCase):

    scenarios = [
        ('dummy_import_failure', {
            'pathname': '/anonymous/',
            'content': 'bogus',
            'content_filename': 'test1.json',
        }),
    ]

    def setUp(self):
        super(BundleDeserializationTestCase, self).setUp()
        self.bundle = fixtures.create_bundle(
            self.pathname, self.content, self.content_filename)
        self.mocker = Mocker()

    def tearDown(self):
        super(BundleDeserializationTestCase, self).tearDown()
        self.bundle.delete()
        self.mocker.restore()
        self.mocker.verify()

    def test_deserialize_failure_leaves_trace(self):
        mock = self.mocker.patch(self.bundle)
        expect(mock._do_deserialize()).throw(Exception("boom"))
        self.mocker.replay()
        self.bundle.deserialize()
        self.assertFalse(self.bundle.is_deserialized)
        self.assertEqual(self.bundle.deserialization_error.error_message, "boom")

    def test_deserialize_ignores_deserialized_bundles(self):
        # just reply as we're not using mocker in this test case 
        self.mocker.replay()
        self.bundle.is_deserialized = True
        self.bundle.deserialize()
        self.assertTrue(self.bundle.is_deserialized)

    def test_deserialize_sets_is_serialized_on_success(self):
        mock = self.mocker.patch(self.bundle)
        expect(mock._do_deserialize())
        self.mocker.replay()
        self.bundle.deserialize()
        self.assertTrue(self.bundle.is_deserialized)

    def test_deserialize_clears_old_error_on_success(self):
        BundleDeserializationError.objects.create(
            bundle = self.bundle,
            error_message="not important").save()
        mock = self.mocker.patch(self.bundle)
        expect(mock._do_deserialize())
        self.mocker.replay()
        self.bundle.deserialize()
        # note we cannot check for self.bundle.deserialization_error
        # directly due to the way django handles operations that affect
        # existing instances (it does not touch them like storm would
        # IIRC).
        self.assertRaises(
            BundleDeserializationError.DoesNotExist,
            BundleDeserializationError.objects.get, bundle=self.bundle)


class TestConstructionTestCase(TestCase):

    scenarios = [
        ('simple1', {
            'test_id': 'org.linaro.testheads.android',
            'name': "Android test suite"}),
        ('simple2', {
            'test_id': 'org.mozilla.unit-tests',
            'name': "Mozilla unit test collection"})
    ]

    def test_construction(self):
        test = Test(test_id = self.test_id, name = self.name)
        test.save()
        self.assertEqual(test.test_id, self.test_id)
        self.assertEqual(test.name, self.name)

    def test_test_id_uniqueness(self):
        test = Test(test_id = self.test_id, name = self.name)
        test.save()
        test2 = Test(test_id = self.test_id)
        self.assertRaises(IntegrityError, test2.save)


class TestCaseConstructionTestCase(TestCase):

    scenarios = [
        ('simple1', {
            'test_id': 'org.linaro.testheads.android',
            'test_case_id': 'testcase1',
            'name': "Boot test"}),
        ('simple2', {
            'test_id': 'org.mozilla.unit-tests',
            'test_case_id': 'testcase125',
            'name': "Rendering test"})
    ]

    def setUp(self):
        super(TestCaseConstructionTestCase, self).setUp()
        self.test = Test(test_id=self.test_id)
        self.test.save()

    def test_construction(self):
        test_case = TestCaseModel(
            test = self.test,
            test_case_id = self.test_case_id,
            name = self.name)
        test_case.save()
        self.assertEqual(self.name, test_case.name)
        self.assertEqual(self.test_case_id, test_case.test_case_id)
        self.assertEqual(self.name, test_case.name)

    def test_test_and_test_case_id_uniqueness(self):
        test_case = TestCaseModel(
            test = self.test,
            test_case_id = self.test_case_id)
        test_case.save()
        test_case2 = TestCaseModel(
            test = self.test,
            test_case_id = self.test_case_id)
        self.assertRaises(IntegrityError, test_case2.save)


class TestRunConstructionTestCase(TestCase):

    _TEST_ID = "test_id"
    _BUNDLE_PATHNAME = "/anonymous/"
    _BUNDLE_CONTENT_FILENAME = "bundle.txt"
    _BUNDLE_CONTENT = "content not relevant"

    def test_construction(self):
        test = Test.objects.create(test_id=self._TEST_ID)
        analyzer_assigned_uuid = '9695b58e-bfe9-11df-a9a4-002163936223'
        analyzer_assigned_date = datetime.datetime(2010, 9, 14, 12, 20, 00)
        time_check_performed = False
        with fixtures.created_bundles([(
            self._BUNDLE_PATHNAME, self._BUNDLE_CONTENT_FILENAME,
            self._BUNDLE_CONTENT), ]) as bundles:
            test_run = TestRun(
                bundle = bundles[0],
                test = test,
                analyzer_assigned_uuid = analyzer_assigned_uuid,
                analyzer_assigned_date = analyzer_assigned_date,
            )
            test_run.save()
            self.assertEqual(test_run.bundle, bundles[0])
            self.assertEqual(test_run.test, test)
            self.assertEqual(test_run.analyzer_assigned_uuid,
                             analyzer_assigned_uuid)


class TestResultDurationTestCase(TestCase):

    scenarios = [
        ('none_is_null', {
            'duration': None,
            'microseconds': None,
        }),
        ('0_is_0', {
            'duration': datetime.timedelta(days=0, seconds=0, microseconds=0),
            'microseconds': 0,
        }),
        ('microseconds_are_just_microseconds', {
            'duration': datetime.timedelta(microseconds=1),
            'microseconds': 1,
        }),
        ('second_is_10e6_microseconds', {
            'duration': datetime.timedelta(seconds=1),
            'microseconds': 10**6,
        }),
        ('day_is_24_times_60_times_60_times_10e6_microseconds', {
            'duration': datetime.timedelta(days=1),
            'microseconds': 24 * 60 * 60 * 10 ** 6,
        }),
        ('microseconds_seconds_and_days_are_used', {
            'duration': datetime.timedelta(days=1, seconds=1, microseconds=1),
            'microseconds': (
                24 * 60 * 60 * (10 ** 6) +
                10 ** 6 +
                1)
        }),
    ]

    def test_duration_to_microseconds(self):
        obj = TestResult()
        obj.duration = self.duration
        self.assertEqual(self.microseconds, obj.microseconds)

    def test_microseconds_to_duration(self):
        obj = TestResult()
        obj.microseconds = self.microseconds
        self.assertEqual(self.duration, obj.duration)


class BundleStreamManagerAllowedForAnyoneTestCase(TestCase):

    _USER = 'user'
    _GROUP = 'group'
    _SLUG = 'slug'

    scenarios = [
        ('empty', {
            'bundle_streams': [],
            'expected_pathnames': [],
            }),
        ('public_streams_are_listed', {
            'bundle_streams': [
                {'slug': ''},
                {'slug': 'other'},
                {'slug': 'and-another'},
                ],
            'expected_pathnames': [
                '/anonymous/',
                '/anonymous/and-another/',
                '/anonymous/other/',
                ],
            }),
        ('private_streams_are_hidden', {
            'bundle_streams': [
                {'user': _USER},
                ],
            'expected_pathnames': [],
            }),
        ('team_streams_are_hidden', {
            'bundle_streams': [
                {'group': _GROUP},
                ],
            'expected_pathnames': [],
            }),
        ('mix_and_match_works', {
            'bundle_streams': [
                {'group': _GROUP, 'slug': _SLUG},
                {'group': _GROUP},
                {'slug': ''},
                {'slug': _SLUG},
                {'user': _GROUP, 'slug': _SLUG},
                {'user': _USER},
                ],
            'expected_pathnames': [
                '/anonymous/',
                '/anonymous/{0}/'.format(_SLUG),
                ],
            }),
        ]

    def test_allowed_for_anyone(self):
        with fixtures.created_bundle_streams(self.bundle_streams):
            pathnames = [bundle_stream.pathname for bundle_stream in
                    BundleStream.objects.allowed_for_anyone().order_by('pathname')]
            self.assertEqual(pathnames, self.expected_pathnames)


class BundleStreamManagerAllowedForUserTestCase(TestCase):

    _USER = 'user'
    _USER2 = 'user2'
    _GROUP = 'group'
    _GROUP2 = 'group2'
    _SLUG = 'slug'

    scenarios = [
        ('empty', {
            'bundle_streams': [],
            'expected_pathnames': [],
            }),
        ('public_streams_are_listed', {
            'bundle_streams': [
                {'slug': ''},
                {'slug': 'other'},
                {'slug': 'and-another'},
                ],
            'expected_pathnames': [
                '/anonymous/',
                '/anonymous/and-another/',
                '/anonymous/other/',
                ],
            }),
        ('owned_private_streams_are_listed', {
            'bundle_streams': [
                {'user': _USER},
                ],
            'expected_pathnames': [
                '/personal/{0}/'.format(_USER),
                ],
            }),
        ('other_private_streams_are_hidden', {
            'bundle_streams': [
                {'user': _USER2},
                ],
            'expected_pathnames': [],
            }),
        ('shared_team_streams_are_listed', {
            'bundle_streams': [
                {'group': _GROUP},
                ],
            'expected_pathnames': [
                '/team/{0}/'.format(_GROUP),
                ],
            }),
        ('other_team_streams_are_hidden', {
            'bundle_streams': [
                {'group': _GROUP2},
                ],
            'expected_pathnames': [],
            }),
        ('mix_and_match_works', {
            'bundle_streams': [
                {'slug': ''},
                {'slug': _SLUG},
                {'user': _USER, 'slug': _SLUG},
                {'user': _USER},
                {'group': _GROUP, 'slug': _SLUG},
                {'group': _GROUP},
                # things which should not be accessible
                {'user': _USER2, 'slug': _SLUG},
                {'user': _USER2},
                {'group': _GROUP2, 'slug': _SLUG},
                {'group': _GROUP2},
                ],
            'expected_pathnames': [
                '/anonymous/',
                '/anonymous/{0}/'.format(_SLUG),
                '/personal/{0}/'.format(_USER),
                '/personal/{0}/{1}/'.format(_USER, _SLUG),
                '/team/{0}/'.format(_GROUP),
                '/team/{0}/{1}/'.format(_GROUP, _SLUG),
                ],
            }),
        ]

    def test_allowed_for_user(self):
        with fixtures.created_bundle_streams(self.bundle_streams) as all:
            user = User.objects.get_or_create(username=self._USER)[0]
            user.save()
            group = Group.objects.get_or_create(name=self._GROUP)[0]
            group.save()
            user.groups.add(group)
            pathnames = [bundle_stream.pathname for bundle_stream in
                    BundleStream.objects.allowed_for_user(user).order_by('pathname')]
            self.assertEqual(pathnames, self.expected_pathnames)


class BundleStreamUploadRightTests(TestCase):

    def test_owner_can_access_personal_stream(self):
        user = User.objects.create(username="test-user")
        bundle_stream = BundleStream.objects.create(user=user)
        self.assertTrue(bundle_stream.can_access(user))

    def test_other_users_cannot_access_personal_streams(self):
        owner = User.objects.create(username="stream-owner")
        unrelated_user = User.objects.create(username="other-user")
        bundle_stream = BundleStream.objects.create(user=owner)
        self.assertFalse(bundle_stream.can_access(unrelated_user))

    def test_anonymous_users_cannot_access_personal_streams(self):
        owner = User.objects.create(username="stream-owner")
        bundle_stream = BundleStream.objects.create(user=owner)
        self.assertFalse(bundle_stream.can_access(None))

    def test_group_member_can_access_team_streams(self):
        group = Group.objects.create(name="members")
        user = User.objects.create(username="user")
        user.groups.add(group)
        bundle_stream = BundleStream.objects.create(group=group)
        self.assertTrue(bundle_stream.can_access(user))

    def test_other_users_cannot_access_team_streams(self):
        group = Group.objects.create(name="members")
        member = User.objects.create(username="user")
        member.groups.add(group)
        unrelated_user = User.objects.create(username="other-user")
        bundle_stream = BundleStream.objects.create(group=group)
        self.assertFalse(bundle_stream.can_access(unrelated_user))

    def test_anonymous_users_cannot_access_team_streams(self):
        group = Group.objects.create(name="members")
        bundle_stream = BundleStream.objects.create(group=group)
        self.assertFalse(bundle_stream.can_access(None))

    def test_anonymous_users_can_access_public_streams(self):
        bundle_stream = BundleStream.objects.create(user=None, group=None)
        self.assertTrue(bundle_stream.can_access(None))

    def test_authorized_users_can_access_public_streams(self):
        user = User.objects.create(username="user")
        bundle_stream = BundleStream.objects.create(user=None, group=None)
        self.assertTrue(bundle_stream.can_access(user))


class BundleTests(TestCase, ObjectFactoryMixIn):

    class Dummy:
        class Bundle:
            @property
            def bundle_stream(self):
                return BundleStream.objects.get_or_create(slug="foobar")[0]
            uploaded_by = None
            content = ContentFile("file content")
            content_filename = "file.txt"

    def test_construction(self):
        dummy, bundle = self.make_and_get_dummy(Bundle)
        bundle.content.save(bundle.content_filename, dummy.content)
        # reset the dummy content file pointer for subsequent tests
        dummy.content.seek(0)
        content = dummy.content.read()

        bundle.save()
        try:
            self.assertEqual(bundle.bundle_stream, dummy.bundle_stream)
            self.assertEqual(bundle.uploaded_by, dummy.uploaded_by)
            #self.assertEqual(bundle.uploaded_on, mocked_value_of_time.now)
            self.assertEqual(bundle.is_deserialized, False)
            self.assertEqual(bundle.content.read(), content)
            self.assertEqual(bundle.content_sha1,
                    hashlib.sha1(content).hexdigest())
            self.assertEqual(bundle.content_filename,
                    dummy.content_filename)
        finally:
            bundle.delete()


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


class DashboardAPITestCase(TestCase):

    def setUp(self):
        super(DashboardAPITestCase, self).setUp()
        self.client = Client()

    def xml_rpc_call(self, method, *args):
        request = xmlrpclib.dumps(tuple(args), methodname=method)
        response = self.client.post("/xml-rpc/",
                data=request,
                content_type="text/xml")
        return xmlrpclib.loads(response.content)[0][0]


class TestClient(Client):

    def login_user(self, user):
        """
        Login as specified user, does not depend on auth backend (hopefully)

        This is based on Client.login() with a small hack that does not
        require the call to authenticate()
        """
        if not 'django.contrib.sessions' in settings.INSTALLED_APPS:
            raise EnvironmentError("Unable to login without django.contrib.sessions in INSTALLED_APPS")
        user.backend = "%s.%s" % ("django.contrib.auth.backends",
                                  "ModelBackend")
        engine = import_module(settings.SESSION_ENGINE)

        # Create a fake request to store login details.
        request = HttpRequest()
        if self.session:
            request.session = self.session
        else:
            request.session = engine.SessionStore()
        login(request, user)

        # Set the cookie to represent the session.
        session_cookie = settings.SESSION_COOKIE_NAME
        self.cookies[session_cookie] = request.session.session_key
        cookie_data = {
            'max-age': None,
            'path': '/',
            'domain': settings.SESSION_COOKIE_DOMAIN,
            'secure': settings.SESSION_COOKIE_SECURE or None,
            'expires': None,
        }
        self.cookies[session_cookie].update(cookie_data)

        # Save the session values.
        request.session.save()


class TestClientTest(TestCase):

    _USER = "user"

    urls = 'dashboard_app.test_urls'

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


class DashboardAPITests(DashboardAPITestCase):

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


class DashboardAPIStreamsTests(DashboardAPITestCase):

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


class DashboardAPIBundlesTests(DashboardAPITestCase):

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


class DashboardAPIBundlesFailureTests(DashboardAPITestCase):

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


class DashboardAPIGetTests(DashboardAPITestCase):

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


class DashboardAPIGetFailureTests(DashboardAPITestCase):

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


class DashboardAPIPutTests(DashboardAPITestCase):

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


class DashboardAPIPutFailureTests(DashboardAPITestCase):

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


class DjangoTestCaseWithScenarios(TestCase):

    scenarios = [
            ('a', {}),
            ('b', {}),
            ]

    def test_database_is_empty_at_start_of_test(self):
        self.assertEqual(BundleStream.objects.all().count(), 0)
        stream = BundleStream.objects.create(slug='')


class BundleStreamListViewAnonymousTest(TestCase):

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


class BundleStreamDetailViewAnonymousTest(TestCase):

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


class ModelWithAttachments(models.Model):
    """
    Test model that uses attachments
    """
    attachments = generic.GenericRelation(Attachment)


class AttachmentTestCase(TestCase):
    _CONTENT = "text"
    _FILENAME = "filename"


    def setUp(self):
        self.obj = ModelWithAttachments.objects.create()

    def tearDown(self):
        self.obj.attachments.all().delete()

    def test_attachment_can_be_added_to_models(self):
        attachment = self.obj.attachments.create(
            content_filename = self._FILENAME, content=None)
        self.assertEqual(attachment.content_object, self.obj)

    def test_attachment_can_be_accessed_via_model(self):
        self.obj.attachments.create(
            content_filename = self._FILENAME, content=None)
        self.assertEqual(self.obj.attachments.count(), 1)
        retrieved_attachment = self.obj.attachments.all()[0]
        self.assertEqual(retrieved_attachment.content_object, self.obj)

    def test_attachment_stores_data(self):
        attachment = self.obj.attachments.create(
            content_filename = self._FILENAME, content=None)
        attachment.content.save(
            self._FILENAME,
            ContentFile(self._CONTENT))
        self.assertEqual(attachment.content_filename, self._FILENAME)
        attachment.content.open()
        try:
            self.assertEqual(attachment.content.read(), self._CONTENT)
        finally:
            attachment.content.close()


def suite():
    import unittest
    from testscenarios.scenarios import generate_scenarios
    loader = unittest.TestLoader()
    test_suite = unittest.TestSuite()
    tests = loader.loadTestsFromName(__name__)
    test_suite.addTests(generate_scenarios(tests))
    return test_suite
