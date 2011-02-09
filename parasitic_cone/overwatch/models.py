from django.db import models


class TestDeviceClass(models.Model):
    """
    Class of test devices.

    Used to create common (equivalent) device groups
    """

    name = models.CharField(
        null=False,
        blank=False,
        max_length=16
    )



class TestDevice(models.Model):
    """
    Test device.
    """

    device_class = models.ForeignKey(
        TestDeviceClass,
        related_name="test_devices",
        null=False,
    )
