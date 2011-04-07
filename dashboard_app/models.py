# Copyright (C) 2010, 2011 Linaro Limited
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
import logging
import traceback

from django import core
from django.contrib.auth.models import (User, Group)
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models, transaction, IntegrityError
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext

from django_restricted_resource.models  import RestrictedResource

from dashboard_app.helpers import BundleDeserializer
from dashboard_app.managers import BundleManager


def _help_max_length(max_length):
    return ungettext(
            u"Maximum length: {0} character",
            u"Maximum length: {0} characters",
            max_length).format(max_length)


class SoftwarePackage(models.Model):
    """
    Model for software packages.
    """
    name = models.CharField(
            max_length = 64,
            verbose_name = _(u"Package name"),
            help_text = _help_max_length(64))

    version = models.CharField(
            max_length = 64,
            verbose_name = _(u"Package version"),
            help_text = _help_max_length(32))

    class Meta:
        unique_together = (('name', 'version'))

    def __unicode__(self):
        return _(u"{name} {version}").format(
                name = self.name,
                version = self.version)

    @property
    def link_to_packages_ubuntu_com(self):
        return u"http://packages.ubuntu.com/{name}".format(name=self.name)

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
            help_text = _help_max_length(512),
            max_length = 512)

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
            verbose_name = _(u"Description"),
            )

    attributes = generic.GenericRelation(NamedAttribute)

    def __unicode__(self):
        return self.description


class BundleStream(RestrictedResource):
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
    PATHNAME_PUBLIC = "public"
    PATHNAME_PRIVATE = "private"
    PATHNAME_PERSONAL = "personal"
    PATHNAME_TEAM = "team"

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

    is_anonymous = models.BooleanField()

    def __unicode__(self):
        return self.pathname

    @models.permalink
    def get_absolute_url(self):
        return ("dashboard_app.test_run_list", [self.pathname])

    def get_test_run_count(self):
        return TestRun.objects.filter(bundle__bundle_stream=self).count()

    def clean(self):
        if self.is_anonymous and not self.is_public:
            raise ValidationError(
                'Anonymous streams must be public')
        return super(BundleStream, self).clean()

    def save(self, *args, **kwargs):
        """
        Save this instance.

        Calls self.clean() to ensure that constraints are met.
        Updates pathname to reflect user/group/slug changes.
        """
        self.pathname = self._calc_pathname()
        self.clean()
        return super(BundleStream, self).save(*args, **kwargs)

    def _calc_pathname(self):
        """
        Pseudo pathname-like ID of this stream.

        This pathname is user visible and will be presented to users
        when they want to interact with this bundle stream. The
        pathnames are unique and this is enforced at database level (the
        user and name are unique together).
        """
        if self.is_anonymous:
            parts = ['', self.PATHNAME_ANONYMOUS]
        else:
            if self.is_public:
                parts = ['', self.PATHNAME_PUBLIC]
            else:
                parts = ['', self.PATHNAME_PRIVATE]
            if self.user is not None:
                parts.append(self.PATHNAME_PERSONAL)
                parts.append(self.user.username)
            elif self.group is not None:
                parts.append(self.PATHNAME_TEAM)
                parts.append(self.group.name)
        if self.slug:
            parts.append(self.slug)
        parts.append('')
        return u"/".join(parts)

    @classmethod
    def parse_pathname(cls, pathname):
        """
        Parse BundleStream pathname.

        Returns user, group, slug, is_public, is_anonymous
        Raises ValueError if the pathname is not well formed
        """
        pathname_parts = pathname.split('/')
        if len(pathname_parts) < 3:
            raise ValueError("Pathname too short: %r" % pathname)
        if pathname_parts[0] != '':
            raise ValueError("Pathname must be absolute: %r" % pathname)
        if pathname_parts[1] == cls.PATHNAME_ANONYMOUS:
            user = None
            group = None
            slug = pathname_parts[2]
            correct_length = 2
            is_anonymous = True
            is_public = True
        else:
            is_anonymous = False
            if pathname_parts[1] == cls.PATHNAME_PUBLIC:
                is_public = True
            elif pathname_parts[1] == cls.PATHNAME_PRIVATE:
                is_public = False
            else:
                raise ValueError("Invalid pathname privacy designator:"
                        " %r (full pathname: %r)" % (pathname_parts[1],
                            pathname))
            if pathname_parts[2] == cls.PATHNAME_PERSONAL:
                if len(pathname_parts) < 4:
                    raise ValueError("Pathname too short: %r" % pathname)
                user = pathname_parts[3]
                group = None
                slug = pathname_parts[4]
                correct_length = 4
            elif pathname_parts[2] == cls.PATHNAME_TEAM:
                if len(pathname_parts) < 4:
                    raise ValueError("Pathname too short: %r" % pathname)
                user = None
                group = pathname_parts[3]
                slug = pathname_parts[4]
                correct_length = 4
            else:
                raise ValueError("Invalid pathname ownership designator:"
                        " %r (full pathname %r)" % (pathname[2],
                            pathname))
        if slug != '':
            correct_length += 1
        if pathname_parts[correct_length:] != ['']:
            raise ValueError("Junk after pathname: %r" % pathname)
        return user, group, slug, is_public, is_anonymous


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
            default = datetime.datetime.utcnow)

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

    objects = BundleManager()

    def __unicode__(self):
        return _(u"Bundle {0} ({1})").format(
                self.pk, self.content_filename)

    class Meta:
        ordering = ['-uploaded_on']

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

    def deserialize(self, prefer_evolution=False):
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
            self._do_deserialize(prefer_evolution)
        except Exception as ex:
            import_error = BundleDeserializationError.objects.get_or_create(
                bundle=self)[0]
            import_error.error_message = str(ex)
            import_error.traceback = traceback.format_exc()
            import_error.save()
        else:
            if self.deserialization_error.count():
                self.deserialization_error.get().delete()
            self.is_deserialized = True
            self.save()

    def _do_deserialize(self, prefer_evolution):
        """
        Deserialize this bundle or raise an exception
        """
        helper = BundleDeserializer()
        helper.deserialize(self, prefer_evolution)

    def get_summary_results(self):
        if self.is_deserialized:
            stats = TestResult.objects.filter(
                test_run__bundle = self).values(
                    'result').annotate(
                        count=models.Count('result'))
            result = dict([
                (TestResult.RESULT_MAP[item['result']], item['count'])
                for item in stats])
            result['total'] = sum(result.values())
            return result

    def delete_files(self, save=False):
        """
        Delete all files related to this bundle.

        This is currently used in test code to clean up after testing.
        """
        self.content.delete(save=save)
        for test_run in self.test_runs.all():
            for attachment in test_run.attachments.all():
                attachment.content.delete(save=save)


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
        help_text = (_("""Units in which measurement value should be
                       interpreted in, for example <q>ms</q>, <q>MB/s</q> etc.
                       There is no semantical meaning inferred from the value of
                       this field, free form text is allowed. <br/>""")
                     + _help_max_length(100)),
        max_length = 100,
        verbose_name = _("Units"))

    class Meta:
        unique_together = (('test', 'test_case_id'))

    def __unicode__(self):
        return self.name or self.test_case_id

    @models.permalink
    def get_absolute_url(self):
        return ("dashboard_app.test_case.details", [self.test.test_id, self.test_case_id])


class SoftwareSource(models.Model):
    """
    Model for representing source reference of a particular project
    """

    project_name = models.CharField(
        max_length = 32,
        help_text = _help_max_length(32),
        verbose_name = _(u"Project Name"),
    )
    branch_url = models.CharField(
        max_length = 256,
        help_text = _help_max_length(256),
        verbose_name = _(u"Branch URL"),
    )
    branch_vcs = models.CharField(
        max_length = 10,
        help_text = _help_max_length(10),
        verbose_name = _(u"Branch VCS"),
    )
    branch_revision = models.CharField(
        max_length = 128,
        help_text = _help_max_length(128),
        verbose_name = _(u"Branch Revision")
    )
    commit_timestamp = models.DateTimeField(
        blank=True,
        null=True,
        help_text = _(u"Date and time of the commit (optional)"),
        verbose_name = _(u"Commit Timestamp")
    )
    
    def __unicode__(self):
        return _(u"{project_name} from branch {branch_url} at revision {branch_revision}").format(
            project_name=self.project_name, branch_url=self.branch_url, branch_revision=self.branch_revision)

    @property
    def is_hosted_on_launchpad(self):
        return self.branch_url.startswith("lp:")

    @property
    def is_tag_revision(self):
        return self.branch_revision.startswith("tag:")

    @property
    def branch_tag(self):
        if self.is_tag_revision:
            return self.branch_revision[len("tag:"):]

    @property
    def link_to_project(self):
        return "http://launchpad.net/{project_name}".format(project_name=self.project_name)

    @property
    def link_to_branch(self):
        if self.is_hosted_on_launchpad:
            return "http://launchpad.net/{branch_url}/".format(branch_url=self.branch_url[len("lp:"):])

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
        max_length = 36,
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

    time_check_performed = models.BooleanField(
        verbose_name = _(u"Time check performed"),
        help_text = _(u"Indicator on wether timestamps in the log file (and any "
                      "data derived from them) should be trusted.<br/>"
                      "Many pre-production or development devices do not "
                      "have a battery-powered RTC and it's not common for "
                      "development images not to synchronize time with "
                      "internet time servers.<br/>"
                      "This field allows us to track tests results that "
                      "<em>certainly</em> have correct time if we ever end up "
                      "with lots of tests results from 1972")
    )

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

    sources = models.ManyToManyField(
        SoftwareSource,
        blank = True,
        related_name = 'test_runs',
        verbose_name = _(u"Software sources"),
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
        return _(u"Test run {0}").format(self.analyzer_assigned_uuid)

    @models.permalink
    def get_absolute_url(self):
        return ("dashboard_app.views.test_run_detail",
                [self.analyzer_assigned_uuid])

    def get_summary_results(self):
        stats = self.test_results.values('result').annotate(
            count=models.Count('result')).order_by()
        result = dict([
            (TestResult.RESULT_MAP[item['result']], item['count'])
            for item in stats])
        result['total'] = sum(result.values())
        return result

    class Meta:
        ordering = ['-import_assigned_date']


class Attachment(models.Model):
    """
    Model for adding attachments to any other models.
    """

    content = models.FileField(
        verbose_name = _(u"Content"),
        help_text = _(u"Attachment content"),
        upload_to = 'attachments',
        null = True)

    content_filename = models.CharField(
        verbose_name = _(u"Content file name"),
        help_text = _(u"Name of the original attachment"),
        max_length = 256)

    mime_type = models.CharField(
        verbose_name = _(u"MIME type"),
        max_length = 64)
    
    public_url = models.URLField(
        verbose_name = _(u"Public URL"),
        max_length = 512,
        blank = True)

    # Content type plumbing
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = generic.GenericForeignKey('content_type', 'object_id')

    def __unicode__(self):
        return self.content_filename

    @models.permalink
    def get_absolute_url(self):
        return ("dashboard_app.views.attachment_detail", [self.pk])

    def get_content_if_possible(self, mirror=False):
        if self.content:
            self.content.open()
            try:
                data = self.content.read()
            finally:
                self.content.close()
        elif self.public_url and mirror:
            import urllib
            stream = urllib.urlopen(self.public_url)
            try:
                data = stream.read()
            except:
                data = None
            else:
                from django.core.files.base import ContentFile
                self.content.save(
                    "attachment-{0}.txt".format(self.pk),
                    ContentFile(data))
            finally:
                stream.close()
        else:
            data = None
        return data


class TestResult(models.Model):
    """
    Model for representing test results.
    """

    RESULT_PASS = 0
    RESULT_FAIL = 1
    RESULT_SKIP = 2
    RESULT_UNKNOWN = 3

    RESULT_MAP = {
        RESULT_PASS: 'pass',
        RESULT_FAIL: 'fail',
        RESULT_SKIP: 'skip',
        RESULT_UNKNOWN: 'unknown'
    }

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

    @property
    def test(self):
        return self.test_run.test

    # Core attributes

    result = models.PositiveSmallIntegerField(
        verbose_name = _(u"Result"),
        help_text = _(u"Result classification to pass/fail group"),
        choices = (
            (RESULT_PASS, _(u"Test passed")),
            (RESULT_FAIL, _(u"Test failed")),
            (RESULT_SKIP, _(u"Test skipped")),
            (RESULT_UNKNOWN, _(u"Unknown outcome")))
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

    microseconds = models.BigIntegerField(
        blank = True,
        null = True
    )

    timestamp = models.DateTimeField(
        blank = True,
        null = True
    )

    relative_index = models.PositiveIntegerField(
        help_text = _(u"The relative order of test results in one test run")
    )

    def __unicode__(self):
        return "Result {0}/{1}".format(self.test_run.analyzer_assigned_uuid, self.relative_index)

    @property
    def result_code(self):
        """
        Stable textual result code that does not depend on locale
        """
        return self.RESULT_MAP[self.result]

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

    @models.permalink
    def get_absolute_url(self):
        return ("dashboard_app.views.test_result_detail",
                [self.pk])

    def related_attachment_available(self):
        """
        Check if there is a log file attached to the test run that has
        the same filename as log filename recorded in the result here.
        """
        try:
            self.related_attachment()
            return True
        except Attachment.DoesNotExist:
            return False

    def related_attachment(self):
        return self.test_run.attachments.get(content_filename=self.filename)

    class Meta:
        ordering = ['relative_index']
        order_with_respect_to = 'test_run'
