"""
This file demonstrates two different styles of tests (one doctest and one
unittest). These will both pass when you run "manage.py test".

Replace these with more appropriate tests for your application.
"""

from django.test import TestCase
from lava.overwatch.models import Device 


class DeviceTests(TestCase):

    def test_get_overwatch_success(self):
        device = Device.objects.create(
            overwatch_driver='dummy')
        from lava.overwatch.drivers.dummy import DummyDriver
        driver = device.get_overwatch()
        self.assertTrue(isinstance(driver, DummyDriver))
