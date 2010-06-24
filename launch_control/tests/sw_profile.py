"""
Test cases for launch_control.sw_profile module
"""

from unittest import TestCase

from launch_control.sw_profile import (SoftwarePackage, SoftwareProfile,
        SoftwareProfileError)
from launch_control.testing.call_helper import ObjectFactory
from launch_control.thirdparty.mocker import (MockerTestCase, expect, ANY)


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


class SoftwareProfileTestCase(MockerTestCase):

    def setUp(self):
        super(SoftwareProfileTestCase, self).setUp()
        self.sw_profile = SoftwareProfile()

    def _mock_installed_apt_pkg(self, name, version):
        pkg = self.mocker.mock()
        expect(pkg.name).result(name)
        expect(pkg.is_installed).result(True)
        expect(pkg.installed.version).result(version)
        return pkg

    def _mock_uninstalled_apt_pkg(self):
        pkg = self.mocker.mock()
        expect(pkg.is_installed).result(False)
        return pkg

    def _mock_apt_cache(self, packages):
        """
        Produce mock-up of apt.Cache() that contains specified packages.
        Users are expected to iterate over the returned instance.
        """
        apt_cache = self.mocker.mock()
        iter(apt_cache)
        self.mocker.result(iter(packages))
        return apt_cache

    def test_find_installed_packages(self):
        pkg1 = self._mock_installed_apt_pkg('foo', '1.0')
        pkg2 = self._mock_uninstalled_apt_pkg()
        apt_cache = self._mock_apt_cache([pkg1, pkg2])
        self.mocker.replay()
        installed_packages = self.sw_profile.find_installed_packages(
                apt_cache=apt_cache)
        self.assertEqual(installed_packages, [SoftwarePackage('foo', '1.0')])

    def test_parse_lsb_release_finds_DISTRIB_DESCRIPTION(self):
        image_id = self.sw_profile._parse_lsb_release(
                "DISTRIB_DESCRIPTION=foobar".splitlines())
        self.assertEqual(image_id, 'foobar')

    def test_parse_lsb_release_fails_on_incomplete_input(self):
        self.assertRaises(SoftwareProfileError,
                self.sw_profile._parse_lsb_release, "".splitlines())

    def test_parse_lsb_release_fails_on_malformed_input(self):
        self.assertRaises(ValueError,
                self.sw_profile._parse_lsb_release, "bonkers".splitlines())

    def test_find_image_id(self):
        # Fake stream that supports context manager protocol
        fake_file = self.mocker.mock()
        fake_file.__enter__()
        fake_file.__exit__(ANY, ANY, ANY)
        # Fake open() that expect to check /etc/lsb-release
        my_open = self.mocker.replace("__builtin__.open")
        expect(my_open('/etc/lsb-release', 'rt')).result(fake_file)
        # Patched sw_profile instance that does not call real
        # _parse_lsb_release() since we're not testing it here
        sw_profile = self.mocker.patch(self.sw_profile)
        expect(sw_profile._parse_lsb_release(ANY)).result('foobar')
        # Ready
        self.mocker.replay()
        self.assertEqual(self.sw_profile.find_image_id(), 'foobar')
