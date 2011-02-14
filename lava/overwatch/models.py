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
        null=True,
    )

    overwatch_driver = models.CharField(
        max_length=255,
        null=False,
        blank=False,
        default="dummy"
    )

    overwatch_config = models.TextField(
        max_length=65535,
        null=False,
        blank=True,
        default=""
    )

    def get_overwatch(self):
        """
        Return an overwatch driver that manages this device
        """
        from pkg_resources import working_set
        drivers = list(working_set.iter_entry_points("lava.overwatch.drivers", self.overwatch_driver))
        if len(drivers) == 0:
            raise ImproperlyConfigured(
                "Unable to load any overwatch drivers for name %r" % (
                    self.overwatch_driver))
        elif len(drivers) > 1:
            raise ImproperlyConfigured(
                "There is more than one overwatch driver for name %r" % (
                    self.overwatch_driver))
        driver_cls = drivers[0].load()
        return driver_cls(self.overwatch_config)
