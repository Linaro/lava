from django.db import models


class DeviceClass(models.Model):
    """
    Class of devices used in the lab.

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

    device_class = models.ForeignKey(
        DeviceClass,
        related_name="devices",
        null=False,
    )
