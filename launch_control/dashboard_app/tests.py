"""
Unit tests of the Dashboard application
"""

from django.test import TestCase
from django.db import IntegrityError

from launch_control.dashboard_app.models import (
        SoftwarePackage,
        )


class SoftwarePackageTestCase(TestCase):

    def test_creation_1(self):
        sw_package = SoftwarePackage.objects.create(name='libfoo', version='1.2.0')
        self.assertEqual(sw_package.name, 'libfoo')
        self.assertEqual(sw_package.version, '1.2.0')

    def test_uniqueness(self):
        SoftwarePackage.objects.create(name='a', version='0')
        self.assertRaises(IntegrityError, SoftwarePackage.objects.create,
                name='a', version='0')
