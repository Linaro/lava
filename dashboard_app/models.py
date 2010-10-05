# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

"""
Database models of the Dashboard application
"""
import datetime
import hashlib
import traceback

from django import core
from django.contrib.auth.models import (User, Group)
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext

from dashboard_app import managers
from dashboard_app.helpers import BundleDeserializer, DocumentError


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
        return _(u"{name}: {value}").format(
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
    PATHNAME_ANONYMOUS = "anonymous"
    PATHNAME_PERSONAL = "personal"
    PATHNAME_TEAM = "team"

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
        return self.pathname

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
                return u"/{prefix}/{user}/".format(
                        prefix = self.PATHNAME_PERSONAL,
                        user = self.user.username)
            else:
                return u"/{prefix}/{user}/{slug}/".format(
                        prefix = self.PATHNAME_PERSONAL,
                        user = self.user.username,
                        slug = self.slug)
        elif self.group is not None:
            if self.slug == "":
                return u"/{prefix}/{group}/".format(
                        prefix = self.PATHNAME_TEAM,
                        group = self.group.name)
            else:
                return u"/{prefix}/{group}/{slug}/".format(
                        prefix = self.PATHNAME_TEAM,
                        group = self.group.name,
                        slug = self.slug)
        else:
            if self.slug == "":
                return u"/{prefix}/".format(
                        prefix = self.PATHNAME_ANONYMOUS)
            else:
                return u"/{prefix}/{slug}/".format(
                        prefix = self.PATHNAME_ANONYMOUS,
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
            try:
                self.content.open('rb')
                sha1 = hashlib.sha1()
                for chunk in self.content.chunks():
                    sha1.update(chunk)
                self.content_sha1 = sha1.hexdigest()
            finally:
                self.content.close()
        return super(Bundle, self).save(*args, **kwargs)

    def deserialize(self):
        """
        Deserialize the contents of this bundle.

        The actual implementation is _do_serialize() this function
        catches any exceptions it might throw and converts them to
        BundleDeserializationError instance. Any previous import errors are
        overwritten.

        Successful import also discards any previous import errors and
        sets is_deserialized to True.
        """
        if self.is_deserialized:
            return
        try:
            self._do_deserialize()
        except Exception as ex:
            import_error = BundleDeserializationError.objects.get_or_create(
                bundle=self)[0]
            import_error.error_message = str(ex)
            import_error.traceback = traceback.format_exc()
            import_error.save()
        else:
            if self.deserialization_error.exists():
                self.deserialization_error.get().delete()
            self.is_deserialized = True
            self.save()

    def _do_deserialize(self):
        """
        Deserialize this bundle or raise an exception
        """
        helper = BundleDeserializer()
        helper.deserialize(self)


class BundleDeserializationError(models.Model):
    """
    Model for representing errors encountered during bundle
    deserialization. There is one instance per bundle limit due to
    unique = True. There used to be a OneToOne field but it didn't work
    with databrowse application.

    The relevant logic for managing this is in the Bundle.deserialize()
    """

    bundle = models.ForeignKey(
        Bundle,
        primary_key = True,
        unique = True,
        related_name = 'deserialization_error'
    )

    error_message = models.CharField(
        max_length = 1024
    )

    traceback = models.TextField(
        max_length = 1 << 15,
    )

    def __unicode__(self):
        return self.error_message


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
        return self.name or self.test_id

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

    units = models.CharField(
        blank = True,
        help_text = _help_max_length(10),
        max_length = 10,
        verbose_name = _("Units"))

    class Meta:
        unique_together = (('test', 'test_case_id'))

    def __unicode__(self):
        return self.name or self.test_case_id

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

    attachments = generic.GenericRelation('Attachment')

    def __unicode__(self):
        return self.analyzer_assigned_uuid

    @models.permalink
    def get_absolute_url(self):
        return ("dashboard_app.test_run.detail",
                [self.analyzer_assigned_uuid])


class Attachment(models.Model):
    """
    Model for adding attachments to any other models.
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


class TestResult(models.Model):
    """
    Model for representing test results.
    """

    RESULT_PASS = 0
    RESULT_FAIL = 1
    RESULT_SKIP = 2
    RESULT_UNKNOWN = 3

    # Context information

    test_run = models.ForeignKey(
        TestRun,
        related_name = "test_results"
    )

    test_case = models.ForeignKey(
        TestCase,
        related_name = "test_results",
        null = True,
        blank = True
    )

    # Core attributes

    result = models.PositiveSmallIntegerField(
        verbose_name = _(u"Result"),
        help_text = _(u"Result classification to pass/fail group"),
        choices = (
            (RESULT_PASS, _(u"pass")),
            (RESULT_FAIL, _(u"fail")),
            (RESULT_SKIP, _(u"skip")),
            (RESULT_UNKNOWN, _(u"unknown")))
    )

    measurement = models.DecimalField(
        blank = True,
        decimal_places = 10,
        help_text = _(u"Arbitrary value that was measured as a part of this test."),
        max_digits = 20,
        null = True,
        verbose_name = _(u"Measurement"),
    )

    # Misc attributes

    filename = models.CharField(
        blank = True,
        max_length = 1024,
        null = True,
    )

    lineno = models.PositiveIntegerField(
        blank = True,
        null = True
    )

    message = models.TextField(
        blank = True,
        max_length = 1024,
        null = True
    )

    microseconds = models.PositiveIntegerField(
        blank = True,
        null = True
    )

    timestamp = models.DateTimeField(
        blank = True,
        null = True
    )

    def __unicode__(self):
        return "#{0} {1}".format(
            self.pk, self.get_result_display())

    # units (via test case)

    @property
    def units(self):
        try:
            return self.test_case.units
        except TestCase.DoesNotExist:
            return None

    # Attributes

    attributes = generic.GenericRelation(NamedAttribute)

    # Duration property

    def _get_duration(self):
        if self.microseconds is None:
            return None
        else:
            return datetime.timedelta(microseconds = self.microseconds)

    def _set_duration(self, duration):
        if duration is None:
            self.microseconds = None
        else:
            if not isinstance(duration, datetime.timedelta):
                raise TypeError("duration must be a datetime.timedelta() instance")
            self.microseconds = (
                duration.microseconds +
                (duration.seconds * 10 ** 6) +
                (duration.days * 24 * 60 * 60 * 10 ** 6))

    duration = property(_get_duration, _set_duration)
