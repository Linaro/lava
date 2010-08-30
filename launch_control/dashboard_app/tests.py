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

    def test_creation_1(self):
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

class BundleStreamTestsMixIn(ObjectFactoryMixIn):

    def test_creation_1(self):
        dummy, bundle_stream = self.make_and_get_dummy(BundleStream)
        bundle_stream.save()
        self.assertEqual(bundle_stream.user, dummy.user)
        self.assertEqual(bundle_stream.group, dummy.group)
        self.assertEqual(bundle_stream.name, dummy.name)
        self.assertEqual(bundle_stream.slug, dummy.slug)

    def test_uniqueness(self):
        bundle_stream1 = self.make(BundleStream)
        bundle_stream1.save()
        bundle_stream2 = self.make(BundleStream)
        self.assertEqual(bundle_stream1.user, bundle_stream2.user)
        self.assertEqual(bundle_stream1.group, bundle_stream2.group)
        self.assertEqual(bundle_stream1.slug, bundle_stream2.slug)
        self.assertRaises(IntegrityError, bundle_stream2.save)


class BundleStreamTests_1(TestCase, BundleStreamTestsMixIn):

    class Dummy:
        class BundleStream:
            name = 'My stream'
            slug = 'my-stream'
            @property
            def user(self):
                user, created = User.objects.get_or_create(username='joe')
                return user
            group = None


class BundleStreamTests_2(TestCase, BundleStreamTestsMixIn):

    class Dummy:
        class BundleStream:
            name = 'My stream'
            slug = 'my-stream'
            user = None
            @property
            def group(self):
                group, created = Group.objects.get_or_create(name='developers')
                return group


class BundleStreamTests_3(TestCase, BundleStreamTestsMixIn):

    class Dummy:
        class BundleStream:
            name = 'My stream'
            slug = 'my-stream'
            user = None
            group = None

class BundleTestsMixIn(ObjectFactoryMixIn):

    def test_construction_1(self):
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


class BundleTests(TestCase, BundleTestsMixIn):

    class Dummy:

        class Bundle:
            @property
            def bundle_stream(self):
                return BundleStream.objects.get_or_create(slug="foobar")[0]
            uploaded_by = None
            content = ContentFile("file content")
            content_filename = "file.txt"
