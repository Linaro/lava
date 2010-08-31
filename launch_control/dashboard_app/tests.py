"""
Unit tests of the Dashboard application
"""

from django.contrib.auth.models import (User, Group)
from django.contrib.contenttypes import generic
from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.test import TestCase

from launch_control.utils.call_helper import ObjectFactoryMixIn
from launch_control.dashboard_app.models import (
        Bundle,
        BundleStream,
        HardwareDevice,
        SoftwarePackage,
        )


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


def uses_scenarios(func):
    """
    Helper decorator for test cases that use scenarios

    Turns wrapped function into a parametrized test case.
    The function needs to accept three arguments:
        self, scenario_name and values
    scenario_name is a string that describes the scenario.
    values is a dictionary of scenario parameters.

    Any test failures will be annotated with scenario name.
    """
    def decorator(self):
        for scenario_name, values in self.scenarios:
            try:
                func(self, scenario_name, values)
            except AssertionError, ex:
                self.fail("Unexpectedly failed with scenario %s: %s" % (
                    scenario_name, ex))
    decorator.__name__ = func.__name__
    return decorator


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

    @uses_scenarios
    def test_creation(self, scenario_name, values):
        bundle_stream = BundleStream.objects.create(
                user=values.get('user'),
                group=values.get('group'),
                name=values.get('name', ''),
                slug=values.get('slug', ''))
        bundle_stream.save()
        self.assertEqual(bundle_stream.user, values.get('user'))
        self.assertEqual(bundle_stream.group, values.get('group'))
        self.assertEqual(bundle_stream.name, values.get('name', ''))
        self.assertEqual(bundle_stream.slug, values.get('slug', ''))

    @uses_scenarios
    def test_team_named_stream(self, scenario_name, values):
        bundle_stream = BundleStream.objects.create(
                user=values.get('user'),
                group=values.get('group'),
                name=values.get('name', ''),
                slug=values.get('slug', ''))
        bundle_stream.save()
        self.assertEqual(bundle_stream.pathname, values['pathname'])

    @uses_scenarios
    def test_pathname_uniqueness(self, scenario_name, values):
        bundle_stream = BundleStream.objects.create(
                user=values.get('user'),
                group=values.get('group'),
                slug=values.get('slug', ''))
        bundle_stream.save()
        self.assertRaises(IntegrityError,
                BundleStream.objects.create,
                user=values.get('user'),
                group=values.get('group'),
                slug=values.get('slug', ''))

    @uses_scenarios
    def test_pathname_update(self, scenario_name, values):
        bundle_stream = BundleStream.objects.create(
                user=values.get('user'),
                group=values.get('group'),
                slug=values.get('slug', ''))
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

        bundle.save()
        self.assertEqual(bundle.bundle_stream, dummy.bundle_stream)
        self.assertEqual(bundle.uploaded_by, dummy.uploaded_by)
        #self.assertEqual(bundle.uploaded_on, mocked_value_of_time.now)
        self.assertEqual(bundle.is_deserialized, False)
        self.assertEqual(bundle.content.read(), dummy.content.read())
        self.assertEqual(bundle.content_filename, dummy.content_filename)

