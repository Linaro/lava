"""
Test for the SoftwarePackage model
"""

from django.db import IntegrityError
from django.test import TestCase

from dashboard_app.models import SoftwarePackage
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

    def test_unicode(self):
        obj = SoftwarePackage(name="foo", version="1.2")
        self.assertEqual(unicode(obj), u"foo 1.2")
