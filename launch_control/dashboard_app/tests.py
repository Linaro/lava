"""
Unit tests of the Dashboard application
"""
import hashlib
import inspect
import xmlrpclib

from django.contrib.auth.models import (User, Group)
from django.contrib.contenttypes import generic
from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.test import TestCase
from django.test.client import Client

from launch_control.dashboard_app import fixtures
from launch_control.utils.call_helper import ObjectFactoryMixIn
from launch_control.dashboard_app.models import (
        Bundle,
        BundleStream,
        HardwareDevice,
        SoftwarePackage,
        )
from launch_control.dashboard_app.dispatcher import (
        DjangoXMLRPCDispatcher,
        xml_rpc_signature,
        )
from launch_control.dashboard_app.xmlrpc import errors


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

    def setUp(self):
        self.user = User.objects.create(username='user')
        self.group = Group.objects.create(name='group')
        self.name = 'Name'
        self.slug = 'slug'
        self.scenarios = (
                ('anonymous-no-slug', {
                    'pathname': '/anonymous/',
                    }),
                ('anonymous-with-slug', {
                    'name': self.name,
                    'slug': self.slug,
                    'pathname': '/anonymous/slug/',
                    }),
                ('personal-no-slug', {
                    'user': self.user,
                    'pathname': '/personal/user/',
                    }),
                ('personal-with-slug', {
                    'user': self.user,
                    'name': self.name,
                    'slug': self.slug,
                    'pathname': '/personal/user/slug/',
                    }),
                ('team-no-slug', {
                    'group': self.group,
                    'pathname': '/team/group/',
                    }),
                ('team-with-slug', {
                    'group': self.group,
                    'name': self.name,
                    'slug': self.slug,
                    'pathname': '/team/group/slug/',
                    }),
                )

    @fixtures.use_test_scenarios
    def test_creation(self, user, group, name='', slug='', **unused):
        bundle_stream = BundleStream.objects.create(user=user,
                group=group, name=name, slug=slug)
        bundle_stream.save()
        self.assertEqual(bundle_stream.user, user)
        self.assertEqual(bundle_stream.group, group)
        self.assertEqual(bundle_stream.name, name)
        self.assertEqual(bundle_stream.slug, slug)

    @fixtures.use_test_scenarios
    def test_team_named_stream(self, user, group, pathname, name='', slug=''):
        bundle_stream = BundleStream.objects.create(user=user,
                group=group, name=name, slug=slug)
        bundle_stream.save()
        self.assertEqual(bundle_stream.pathname, pathname)

    @fixtures.use_test_scenarios
    def test_pathname_uniqueness(self, user, group, pathname, name='', slug=''):
        bundle_stream = BundleStream.objects.create(user=user,
                group=group, name=name, slug=slug)
        bundle_stream.save()
        self.assertRaises(IntegrityError,
                BundleStream.objects.create,
                user=user, group=group, slug=slug, name=name)

    @fixtures.use_test_scenarios
    def test_pathname_update(self, user, group, pathname, name='', slug=''):
        bundle_stream = BundleStream.objects.create(user=user,
                group=group, name=name, slug=slug)
        bundle_stream.save()
        old_pathname = bundle_stream.pathname
        bundle_stream.slug += "-changed"
        bundle_stream.save()
        self.assertNotEqual(bundle_stream.pathname, old_pathname)
        self.assertEqual(bundle_stream.pathname,
                bundle_stream._calc_pathname())


class BundleStreamUploadRightTests(TestCase):

    def test_owner_can_upload(self):
        user = User.objects.create(username="test-user")
        bundle_stream = BundleStream.objects.create(user=user)
        self.assertTrue(bundle_stream.can_upload(user))

    def test_other_users_cannot_upload_to_personal_streams(self):
        owner = User.objects.create(username="stream-owner")
        unrelated_user = User.objects.create(username="other-user")
        bundle_stream = BundleStream.objects.create(user=owner)
        self.assertFalse(bundle_stream.can_upload(unrelated_user))

    def test_anonymous_users_cannot_upload_to_personal_streams(self):
        owner = User.objects.create(username="stream-owner")
        bundle_stream = BundleStream.objects.create(user=owner)
        self.assertFalse(bundle_stream.can_upload(None))

    def test_group_memer_can_upload_to_team_streams(self):
        group = Group.objects.create(name="members")
        user = User.objects.create(username="user")
        user.groups.add(group)
        bundle_stream = BundleStream.objects.create(group=group)
        self.assertTrue(bundle_stream.can_upload(user))

    def test_other_users_cannot_upload_to_team_streams(self):
        group = Group.objects.create(name="members")
        member = User.objects.create(username="user")
        member.groups.add(group)
        unrelated_user = User.objects.create(username="other-user")
        bundle_stream = BundleStream.objects.create(group=group)
        self.assertFalse(bundle_stream.can_upload(unrelated_user))

    def test_anonymous_users_cannot_upload_to_team_streams(self):
        group = Group.objects.create(name="members")
        bundle_stream = BundleStream.objects.create(group=group)
        self.assertFalse(bundle_stream.can_upload(None))

    def test_anonymous_users_can_upload_to_public_streams(self):
        bundle_stream = BundleStream.objects.create(user=None, group=None)
        self.assertTrue(bundle_stream.can_upload(None))

    def test_authorized_users_can_upload_to_public_streams(self):
        user = User.objects.create(username="user")
        bundle_stream = BundleStream.objects.create(user=None, group=None)
        self.assertTrue(bundle_stream.can_upload(user))


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


class DjangoXMLRPCDispatcherTest(TestCase):

    def setUp(self):
        super(DjangoXMLRPCDispatcherTest, self).setUp()
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


class DashboardAPITest(TestCase):

    def setUp(self):
        super(DashboardAPITest, self).setUp()
        self.client = Client()

    def xml_rpc_call(self, method, *args):
        request = xmlrpclib.dumps(tuple(args), methodname=method)
        response = self.client.post("/xml-rpc/",
                data=request,
                content_type="text/xml")
        return xmlrpclib.loads(response.content)[0][0]

    def test_xml_rpc_help_returns_200(self):
        response = self.client.get("/xml-rpc/")
        self.assertEqual(response.status_code, 200)

    def test_help_page_lists_all_methods(self):
        from launch_control.dashboard_app.views import DashboardDispatcher as dispatcher
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
        from launch_control.dashboard_app import __version__
        self.assertEqual(self.xml_rpc_call('version'),
                ".".join(map(str, __version__)))

    @fixtures.use_test_scenarios(
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
            )
    def test_streams(self, streams, expected_response):
        with fixtures.created_bundle_streams(streams):
            response = self.xml_rpc_call('streams')
            self.assertEqual(response, expected_response)


    @fixtures.use_test_scenarios(
            ('empty', {
                'query': '/anonymous/',
                'bundles': [],
                'expected_results': [],
                }),
            ('several_bundles_we_can_see', {
                'query': '/anonymous/',
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
                'bundles': [
                    ('/anonymous/', 'test3.json', '{}'),
                    ('/anonymous/other/', 'test4.json', '{"x": true}'),
                    ],
                'expected_results': [{
                    'content_filename': 'test4.json',
                    'content_sha1': 'bac148f29c35811441a7b4746a022b04c65bffc0',
                    }],
                }),
            ('several_bundles_in_bogus_pathname', {
                'query': '/bogus/',
                'bundles': [
                    ('/anonymous/', 'test5.json', '{}'),
                    ],
                'expected_results': [],
                }),
            )
    def test_bundles(self, bundles, query, expected_results):
        """
        Make a bunch of bundles (all in a public branch) and check that
        they are returned by the XML-RPC request.
        """
        with fixtures.created_bundles(bundles):
            results = self.xml_rpc_call('bundles', query)
            self.assertEqual(len(results), len(expected_results))
            with fixtures.test_loop(zip(results, expected_results)) as loop_items:
                for result, expected_result in loop_items:
                    self.assertEqual(
                            result['content_filename'],
                            expected_result['content_filename'])
                    self.assertEqual(
                            result['content_sha1'],
                            expected_result['content_sha1'])

    @fixtures.use_test_scenarios(
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
            )
    def test_get(self, content_sha1, bundles, expected_result):
        """
        Make a bunch of bundles (all in a public branch) and check that
        we can get them back by calling get()
        """
        with fixtures.created_bundles(bundles):
            result = self.xml_rpc_call('get', content_sha1)
            self.assertTrue(isinstance(result, dict))
            self.assertEqual(
                    result['content_filename'],
                    expected_result['content_filename'])
            self.assertEqual(
                    result['content'],
                    expected_result['content'])
