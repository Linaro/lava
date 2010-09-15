"""
Database models of the Dashboard application
"""
import hashlib

from django import core
from django.contrib.auth.models import (User, Group)
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext

from dashboard_app import managers


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

    class Meta:
        unique_together = (('name', 'version'))

    def __unicode__(self):
        return _(u"{name} {version}").format(
                name = self.name,
                version = self.version)

    @models.permalink
    def get_absolute_url(self):
        return ("dashboard_app.sw-package.detail", [self.name, self.version])


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
            choices = (
                (u"device.cpu", _(u"CPU")),
                (u"device.mem", _(u"Memory")),
                (u"device.usb", _(u"USB device")),
                (u"device.pci", _(u"PCI device")),
                (u"device.board", _(u"Board/Motherboard"))),
            help_text = _(u"One of pre-defined device types"),
            max_length = 32,
            verbose_name = _(u"Device Type"),
            )

    description = models.CharField(
            help_text = _(u"Human readable device summary.") + " " + _help_max_length(256),
            max_length = 256,
            verbose_name = _(u"Description."),
            )

    attributes = generic.GenericRelation(NamedAttribute)

    def __unicode__(self):
        return self.description

    @models.permalink
    def get_absolute_url(self):
        return ("dashboard_app.hw-device.detail", [self.pk])


class BundleStream(models.Model):
    """
    Model for "streams" of bundles.

    Basically it's a named collection of bundles, like directory just
    without the nesting. A simple ACL scheme is also supported,
    a bundle may be uploaded by:
        - specific user when user field is set
        - users of a specific group when group field is set
        - anyone when neither user nor group is set
    """
    user = models.ForeignKey(User,
            blank = True,
            help_text = _("User owning this stream (do not set when group is also set)"),
            null = True,
            verbose_name = _(u"User"),
            )

    group = models.ForeignKey(Group,
            blank = True,
            help_text = _("Group owning this stream (do not set when user is also set)"),
            null = True,
            verbose_name = _(u"Group"),
            )

    slug = models.CharField(
            blank = True,
            help_text = (_(u"Name that you will use when uploading bundles.")
                + " " + _help_max_length(64)),
            max_length = 64,
            verbose_name = _(u"Slug"),
            )

    name = models.CharField(
            blank = True,
            help_text = _help_max_length(64),
            max_length = 64,
            verbose_name = _(u"Name"),
            )

    pathname = models.CharField(
            max_length = 128,
            editable = False,
            unique = True,
            )

    objects = managers.BundleStreamManager()

    def __unicode__(self):
        return _(u"Bundle stream {pathname}").format(
                pathname = self.pathname)

    @models.permalink
    def get_absolute_url(self):
        return ("dashboard_app.bundle_stream_detail", [self.pathname])

    def save(self, *args, **kwargs):
        """
        Save this instance.

        Calls self.clean() to ensure that constraints are met.
        Updates pathname to reflect user/group/slug changes.
        """
        self.pathname = self._calc_pathname()
        self.clean()
        return super(BundleStream, self).save(*args, **kwargs)

    def clean(self):
        """
        Validate instance.

        Makes sure that user and name are not set at the same time
        """
        if self.user is not None and self.group is not None:
            raise core.exceptions.ValidationError('BundleStream cannot '
                    'have both user and name set at the same time')

    def can_access(self, user):
        """
        Returns true if given user can access the contents of this this
        stream.
        """
        if user is None:
            return self.user is None and self.group is None
        else:
            if self.user is not None:
                return self.user.username == user.username
            elif self.group is not None:
                return self.group in user.groups.all()
            else:
                return True

    def _calc_pathname(self):
        """
        Pseudo pathname-like ID of this stream.

        This pathname is user visible and will be presented to users
        when they want to interact with this bundle stream. The
        pathnames are unique and this is enforced at database level (the
        user and name are unique together).
        """
        if self.user is not None:
            if self.slug == "":
                return u"/personal/{user}/".format(
                        user = self.user.username)
            else:
                return u"/personal/{user}/{slug}/".format(
                        user = self.user.username,
                        slug = self.slug)
        elif self.group is not None:
            if self.slug == "":
                return u"/team/{group}/".format(
                        group = self.group.name)
            else:
                return u"/team/{group}/{slug}/".format(
                        group = self.group.name,
                        slug = self.slug)
        else:
            if self.slug == "":
                return u"/anonymous/"
            else:
                return u"/anonymous/{slug}/".format(
                        slug = self.slug)


class Bundle(models.Model):
    """
    Model for "Dashboard Bundles"
    """
    bundle_stream = models.ForeignKey(BundleStream,
            verbose_name = _(u"Stream"),
            related_name = 'bundles')

    uploaded_by = models.ForeignKey(User,
            verbose_name = _(u"Uploaded by"),
            help_text = _(u"The user who submitted this bundle"),
            related_name = 'uploaded_bundles',
            null = True,
            blank = True)

    uploaded_on = models.DateTimeField(
            verbose_name = _(u"Uploaded on"),
            editable = False,
            auto_now_add = True)

    is_deserialized = models.BooleanField(
            verbose_name = _(u"Is deserialized"),
            help_text = _(u"Set when document has been analyzed and loaded"
                " into the database"),
            editable = False)

    content = models.FileField(
            verbose_name = _(u"Content"),
            help_text = _(u"Document in Dashboard Bundle Format 1.0"),
            upload_to = 'bundles',
            null = True)

    content_sha1 = models.CharField(
            editable = False,
            max_length = 40,
            null = True,
            unique = True)

    content_filename = models.CharField(
            verbose_name = _(u"Content file name"),
            help_text = _(u"Name of the originally uploaded bundle"),
            max_length = 256)

    def __unicode__(self):
        return _(u"Bundle {0} ({1})").format(
                self.pk, self.content_filename)

    @models.permalink
    def get_absolute_url(self):
        return ("dashboard_app.bundle.detail", [self.pk])

    def save(self, *args, **kwargs):
        if self.content:
            sha1 = hashlib.sha1()
            for chunk in self.content.chunks():
                sha1.update(chunk)
            self.content_sha1 = sha1.hexdigest()
            self.content.seek(0)
        return super(Bundle, self).save(*args, **kwargs)


class Test(models.Model):
    """
    Model for representing tests.

    Test is a collection of individual test cases.
    """
    test_id = models.CharField(
        max_length = 64,
        verbose_name = _("Test ID"),
        unique = True,
        help_text = _help_max_length(64))

    name = models.CharField(
        blank = True,
        help_text = _help_max_length(64),
        max_length = 64,
        verbose_name = _(u"Name"))

    def __unicode__(self):
        return _(u"Test {0}").format(self.name or self.test_id)

    @models.permalink
    def get_absolute_url(self):
        return ('dashboard_app.test.detail', [self.test_id])


class TestCase(models.Model):
    """
    Model for representing test cases.

    Test case is a unique component of a specific test.
    Test cases allow for relating to test results.
    """
    test = models.ForeignKey(
        Test,
        related_name='test_cases')

    test_case_id = models.CharField(
        help_text = _help_max_length(100),
        max_length = 100,
        verbose_name = _("Test case ID"))

    name = models.CharField(
        blank = True,
        help_text = _help_max_length(100),
        max_length = 100,
        verbose_name = _("Name"))

    class Meta:
        unique_together = (('test', 'test_case_id'))

    def __unicode__(self):
        return "Test case {0}".format(self.name or self.test_case_id)

    @models.permalink
    def get_absolute_url(self):
        return ("dashboard_app.test_case.details", [self.test.test_id, self.test_case_id])


class TestRun(models.Model):
    """
    Model for representing test runs.

    Test run is an act of running a Test in a certain context. The
    context is described by the software and hardware environment.  In
    addition to those properties each test run can have arbitrary named
    properties for additional context that is not reflected in the
    database directly.

    Test runs have global identity exists beyond the lifetime of
    bundle that essentially encapsulates test run information should
    store the UUID that was generated at the time the document is made.
    the dashboard application. The software that prepares the dashboard
    """

    # Meta-data

    bundle = models.ForeignKey(
        Bundle,
        related_name = 'test_runs',
    )

    test = models.ForeignKey(
        Test,
        related_name = 'test_runs',
    )

    analyzer_assigned_uuid = models.CharField(
        help_text = _(u"You can use uuid.uuid1() to generate a value"),
        max_length = 16,
        unique = True,
        verbose_name = _(u"Analyzer assigned UUID"),
    )

    analyzer_assigned_date = models.DateTimeField(
        verbose_name = _(u"Analyzer assigned date"),
        help_text = _(u"Time stamp when the log was processed by the log"
                      " analyzer"),
    )

    import_assigned_date = models.DateTimeField(
        verbose_name = _(u"Import assigned date"),
        help_text = _(u"Time stamp when the bundle was imported"),
        auto_now_add = True,
    )

    time_check_performed = models.BooleanField()

    # Software Context

    sw_image_desc = models.CharField(
        blank = True,
        max_length = 100,
        verbose_name = _(u"Operating System Image"),
    )

    packages = models.ManyToManyField(
        SoftwarePackage,
        blank = True,
        related_name = 'test_runs',
        verbose_name = _(u"Software packages"),
    )

    # Hardware Context

    devices = models.ManyToManyField(
        HardwareDevice,
        blank = True,
        related_name = 'test_runs',
        verbose_name = _(u"Hardware devices"),
    )

    # Attributes

    attributes = generic.GenericRelation(NamedAttribute)

    # Attachments

    attachments = generic.GenericRelation(Attachment)

    def __unicode__(self):
        return _(u"TestRun {uuid}").format(uuid=self.analyzer_assigned_uuid)

    @models.permalink
    def get_absolute_url(self):
        return ("dashboard_app.test_run.detail",
                [self.analyzer_assigned_uuid])


class Attachment(models.Model):
    """
    Model for adding attachments to any other models.

    Example:
        class Foo(Model):
            attributes = generic.GenericRelation(NamedAttribute)
    """

    content = models.FileField(
        verbose_name = _(u"Content"),
        help_text = _(u"Attachment content"), 
        upload_to = 'attachments',
        null = True, 
        # This is only true because we want to name the attached file
        # with the primary key as the filename component and we need to
        # save the Attachment instance with NULL content to do that
    )

    content_filename = models.CharField(
        verbose_name = _(u"Content file name"),
        help_text = _(u"Name of the original attachment"),
        max_length = 256)

    # Content type plumbing
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = generic.GenericForeignKey('content_type', 'object_id')

    def __unicode__(self):
        return self.content_filename
