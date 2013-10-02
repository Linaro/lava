"""
Tests for the Bundle model
"""
import hashlib

from django.core.files.base import ContentFile
from django.test import TestCase
from django_testscenarios.ubertest import TestCaseWithScenarios
from mocker import Mocker, expect

from dashboard_app.tests import fixtures
from dashboard_app.models import (
    Bundle,
    BundleDeserializationError,
    BundleStream,
)
from dashboard_app.tests.call_helper import ObjectFactoryMixIn


class BundleTests(TestCase, ObjectFactoryMixIn):

    class Dummy:
        class Bundle:
            @property
            def bundle_stream(self):
                from django.contrib.auth.models import User
                user = User.objects.get_or_create(username="dummy_user")[0]
                return BundleStream.objects.get_or_create(slug="foobar", user=user)[0]
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
            bundle.content.open()
            self.assertEqual(bundle.content.read(), content)
            bundle.content.close()
            self.assertEqual(bundle.content_sha1,
                    hashlib.sha1(content).hexdigest())
            self.assertEqual(bundle.content_filename,
                    dummy.content_filename)
        finally:
            bundle.delete_files()

    def test_unicode(self):
        obj = Bundle(content_filename="file.json", pk=1)
        self.assertEqual(unicode(obj), u"Bundle None")


class BundleDeserializationTests(TestCaseWithScenarios):

    scenarios = [
        ('dummy_import_failure', {
            'pathname': '/public/personal/admin/',
            'is_public': 'true',
            'content': 'bogus',
            'content_filename': 'test1.json',
        }),
    ]

    def setUp(self):
        super(BundleDeserializationTests, self).setUp()
        self.bundle = fixtures.create_bundle(
            self.pathname, self.content, self.content_filename)
        self.mocker = Mocker()

    def tearDown(self):
        self.bundle.delete_files()
        self.mocker.restore()
        self.mocker.verify()
        super(BundleDeserializationTests, self).tearDown()

    def test_deserialize_failure_leaves_trace(self):
        mock = self.mocker.patch(self.bundle)
        expect(mock._do_deserialize(False)).throw(Exception("boom"))
        self.mocker.replay()
        self.bundle.deserialize(False)
        self.assertFalse(self.bundle.is_deserialized)
        self.assertEqual(self.bundle.deserialization_error.error_message, "boom")

    def test_deserialize_ignores_deserialized_bundles(self):
        # just reply as we're not using mocker in this test case 
        self.mocker.replay()
        self.bundle.is_deserialized = True
        self.bundle.deserialize(False)
        self.assertTrue(self.bundle.is_deserialized)

    def test_deserialize_sets_is_serialized_on_success(self):
        mock = self.mocker.patch(self.bundle)
        expect(mock._do_deserialize(False))
        self.mocker.replay()
        self.bundle.deserialize(False)
        self.assertTrue(self.bundle.is_deserialized)

    def test_deserialize_clears_old_error_on_success(self):
        BundleDeserializationError.objects.create(
            bundle = self.bundle,
            error_message="not important").save()
        mock = self.mocker.patch(self.bundle)
        expect(mock._do_deserialize(False))
        self.mocker.replay()
        self.bundle.deserialize(False)
        # note we cannot check for self.bundle.deserialization_error
        # directly due to the way django handles operations that affect
        # existing instances (it does not touch them like storm would
        # IIRC).
        self.assertRaises(
            BundleDeserializationError.DoesNotExist,
            BundleDeserializationError.objects.get, bundle=self.bundle)
