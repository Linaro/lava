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


class TestTag(TestCase):

    def make_device(self):
        device_type = models.DeviceType(name="nice_board")
        device_type.save()
        device = models.Device(device_type=device_type)
        device.save()
        return device

    def test_add_tag(self):
        device = self.make_device()
        device.add_tag('tagname')
        tag = models.Tag.objects.get(name='tagname')
        self.assertIn(tag, device.tags.all())

class TestTestJob(TestCase):

    def setUp(self):
        self._counter = 0

    def getUniqueName(self):
        self._counter += 1
        return 'name' + str(self._counter)

    def make_device_type(self):
        device_type = models.DeviceType(name=self.getUniqueName())
        device_type.save()
        return device_type

    def make_test_job(self, device_type=None):
        if device_type is None:
            device_type = self.make_device_type()
        job = models.TestJob(
            device_type=device_type,
            timeout=10)
        job.save()
        return job

    def make_device(self, device_type=None):
        if device_type is None:
            device_type = self.make_device_type()
        device = models.Device(device_type=device_type)
        device.save()
        return device

    def test_available_devices_no_devices(self):
        job = self.make_test_job()
        self.assertEquals([], list(job.available_devices()))

    def test_available_devices_device_of_correct_type_no_tags(self):
        device_type = self.make_device_type()
        job = self.make_test_job(device_type=device_type)
        device = self.make_device(device_type=device_type)
        self.assertEquals(
            [device], list(job.available_devices()))

    def test_available_devices_device_of_incorrect_type_no_tags(self):
        device_type1 = self.make_device_type()
        device_type2 = self.make_device_type()
        job = self.make_test_job(device_type=device_type1)
        self.make_device(device_type=device_type2)
        self.assertEquals(
            [], list(job.available_devices()))

    def test_available_devices_running_device_of_correct_type_no_tags(self):
        device_type = self.make_device_type()
        job = self.make_test_job(device_type=device_type)
        device = self.make_device(device_type=device_type)
        device.status = models.Device.RUNNING
        device.save()
        self.assertEquals(
            [], list(job.available_devices()))

    def test_available_devices_offline_device_of_correct_type_no_tags(self):
        device_type = self.make_device_type()
        job = self.make_test_job(device_type=device_type)
        device = self.make_device(device_type=device_type)
        device.status = models.Device.OFFLINE
        device.save()
        self.assertEquals(
            [], list(job.available_devices()))

    def test_available_devices_device_of_correct_type_missing_tag(self):
        device_type = self.make_device_type()
        job = self.make_test_job(device_type=device_type)
        job.add_tag('tagname')
        self.make_device(device_type=device_type)
        self.assertEquals(
            [], list(job.available_devices()))

