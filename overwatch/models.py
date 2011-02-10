from django.core.exceptions import ImproperlyConfigured
from django.db import models


class DeviceType(models.Model):
    """
    Type of devices used in the lab.

    Used to create common (equivalent) device groups
    """

    name = models.CharField(
        null=False,
        blank=False,
        max_length=64
    )


class Device(models.Model):
    """
    Test device.
    """

    device_type = models.ForeignKey(
        DeviceType,
        related_name="devices",
        null=False,
    )

