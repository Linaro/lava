"""
Database models of the Dashboard application
"""

from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext


def _help_max_length(max_length):
    return ungettext(
            u"Maximum length: {0} character",
            u"Maximum length: {0} characters",
            max_length).format(max_length)


class SoftwarePackage(models.Model):
    """
    Model for software packages.

    This class mirrors launch_control.models.SoftwarePackage.
    """
    name = models.CharField(
            max_length = 64,
            verbose_name = _(u"Package name"),
            help_text = _help_max_length(64))

    version = models.CharField(
            max_length = 32,
            verbose_name = _(u"Package version"),
            help_text = _help_max_length(32))

    def __unicode__(self):
        return _(u"{name} {version}").format(
                name = self.name,
                version = self.version)

    class Meta:
        unique_together = (('name', 'version'))


class NamedAttribute(models.Model):
    """
    Model for adding generic named attributes
    to arbitrary other model instances.

    Example:
        class Foo(Model):
            attributes = generic.GenericRelation(NamedAttribute)
    """

    name = models.CharField(
            help_text = _help_max_length(32),
            max_length = 32)

    value = models.CharField(
            help_text = _help_max_length(256),
            max_length = 256)

    # Content type plumbing
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = generic.GenericForeignKey('content_type', 'object_id')

    def __unicode__(self):
        return _(u"Attribute {name}: {value}").format(
                name = self.name,
                value = self.value)

    class Meta:
        unique_together = (('object_id', 'name'))


class HardwareDevice(models.Model):
    """
    Model for hardware devices

    All devices are simplified into an instance of pre-defined class
    with arbitrary key-value attributes.
    """
    device_type = models.CharField(
            verbose_name = _(u"Device Type"),
            help_text = _(u"One of pre-defined device types"),
            max_length = 32,
            choices = (
                (u"device.cpu", _(u"CPU")),
                (u"device.mem", _(u"Memory")),
                (u"device.usb", _(u"USB device")),
                (u"device.pci", _(u"PCI device")),
                (u"device.board", _(u"Board/Motherboard"))))

    description = models.CharField(
            verbose_name = _(u"Description"),
            help_text = (_(u"Human readable device summary.")
                + " " + _help_max_length(256)),
            max_length = 256)

    attributes = generic.GenericRelation(NamedAttribute)
