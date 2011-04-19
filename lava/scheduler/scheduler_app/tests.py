"""
This file demonstrates two different styles of tests (one doctest and one
unittest). These will both pass when you run "manage.py test".

Replace these with more appropriate tests for your application.
"""

from django.test import TestCase
from lava.scheduler.scheduler_app import models

class TestDeviceType(TestCase):

    def test_find_devices_by_type_returns_empty_when_no_devices(self):
        device_type = models.DeviceType(name="nice_board")
        self.assertEquals(
            [], list(models.Device.find_devices_by_type(device_type)))

    def test_find_devices_by_type_returns_matching_device(self):
        device_type = models.DeviceType(name="nice_board")
        device_type.save()
        device = models.Device(device_type=device_type)
        device.save()
        self.assertEquals(
            [device], list(models.Device.find_devices_by_type(device_type)))

    def test_find_devices_by_type_does_not_return_non_matching_device(self):
        device_type1 = models.DeviceType(name="nice_board")
        device_type1.save()
        device_type2 = models.DeviceType(name="nasty_board")
        device_type2.save()
        device = models.Device(device_type=device_type1)
        device.save()
        self.assertEquals(
            [], list(models.Device.find_devices_by_type(device_type2)))
