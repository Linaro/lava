"""
Test cases for launch_control.sw_profile module
"""

from unittest import TestCase

from launch_control.sw_profile import (SoftwarePackage, SoftwareProfile,
        SoftwareProfileError)
from launch_control.testing.call_helper import ObjectFactory


class DummySoftwarePackage(object):
    """ Dummy values for constructing SoftwarePackage instances """
    name = "foo"
    version = "1.2-ubuntu1"

class SoftwarePackageTestCase(TestCase):

    def setUp(self):
        self.factory = ObjectFactory(SoftwarePackage, DummySoftwarePackage)

class Construction(SoftwarePackageTestCase):

    def test_construction(self):
        """ Construction works correctly """
        pkg = self.factory()
        self.assertEqual(pkg.name, self.factory.dummy.name)
        self.assertEqual(pkg.version, self.factory.dummy.version)

class IdenticalPackages(SoftwarePackageTestCase):

    def setUp(self):
        super(IdenticalPackages, self).setUp()
        self.pkg1 = self.factory()
        self.pkg2 = self.factory(name=self.pkg1.name,
                version=self.pkg1.version)

    def test_identical_packages_are_identical(self):
        self.assertEqual(self.pkg1, self.pkg2)
        self.assertFalse(self.pkg1 < self.pkg2)
        self.assertFalse(self.pkg2 < self.pkg1)

    def test_identical_packages_hash_to_same_value(self):
        self.assertEqual(hash(self.pkg1), hash(self.pkg2))


class PackagesWithDifferentNames(SoftwarePackageTestCase):

    def setUp(self):
        super(PackagesWithDifferentNames, self).setUp()
        self.pkg1 = self.factory()
        self.pkg2 = self.factory(name=self.pkg1.name + "other",
                version=self.pkg1.version)

    def test_packages_with_different_names_are_different(self):
        self.assertNotEqual(self.pkg1, self.pkg2)

    def test_packages_with_different_names_hash_to_different_values(self):
        self.assertNotEqual(hash(self.pkg1), hash(self.pkg2))


class PackagesWithDifferentVersions(SoftwarePackageTestCase):

    def setUp(self):
        super(PackagesWithDifferentVersions, self).setUp()
        self.pkg1 = self.factory()
        self.pkg2 = self.factory(name=self.pkg1.name,
                version=self.pkg1.version + "other")

    def test_packages_with_different_versions_hash_to_different_values(self):
        self.assertNotEqual(hash(self.pkg1), hash(self.pkg2))

    def test_packages_with_different_versions_are_different(self):
        self.assertNotEqual(self.pkg1, self.pkg2)

class PackageVersionComparison(SoftwarePackageTestCase):
    # XXX: There is no point in testing odd versions agains each other
    # as we didn't really write the comparator for that.
    # Besides after googling for an hour I *still* cannot find
    # any Debian-blessed document explaining the format.

    def test_obvious(self):
        pkg1 = self.factory(version='1.0')
        pkg2 = self.factory(version='2.0')
        self.assertTrue(pkg1 < pkg2)
        self.assertTrue(pkg1 <= pkg2)
        self.assertFalse(pkg1 == pkg2)
        self.assertFalse(pkg1 >= pkg2)
        self.assertFalse(pkg1 > pkg2)

