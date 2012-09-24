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
import errno
import gzip
import hashlib
import logging
import os
import simplejson
import traceback
import contextlib

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.files import locks, File
from django.core.files.storage import FileSystemStorage
from django.core.mail import send_mail
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models.fields import FieldDoesNotExist
from django.db.models.signals import post_delete
from django.db.models.sql.aggregates import Aggregate as SQLAggregate
from django.dispatch import receiver
from django.template import Template, Context
from django.template.defaultfilters import filesizeformat
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext

from django_restricted_resource.models  import RestrictedResource
from lava_projects.models import Project
from linaro_dashboard_bundle.io import DocumentIO

from dashboard_app.helpers import BundleDeserializer
from dashboard_app.managers import BundleManager, TestRunDenormalizationManager
from dashboard_app.repositories import RepositoryItem 
from dashboard_app.repositories.data_report import DataReportRepository
from dashboard_app.repositories.data_view import DataViewRepository
from dashboard_app.signals import bundle_was_deserialized 


# Fix some django issues we ran into
from dashboard_app.patches import patch
patch()


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
            max_length = 128,
            verbose_name = _(u"Package name"),
            help_text = _help_max_length(128))

    version = models.CharField(
            max_length = 128,
            verbose_name = _(u"Package version"),
            help_text = _help_max_length(128))

    class Meta:
        unique_together = (('name', 'version'))

    def __unicode__(self):
        return _(u"{name} {version}").format(
                name = self.name,
                version = self.version)

    @property
    def link_to_packages_ubuntu_com(self):
        return u"http://packages.ubuntu.com/{name}".format(name=self.name)


class SoftwarePackageScratch(models.Model):
    """
    Staging area for SoftwarePackage data.

    The code that keeps SoftwarePackage dumps data into here before more
    carefully inserting it into the real SoftwarePackage table.

    No data should ever be committed in this table.  It would be a temporary
    table, but oddities in how the sqlite DB-API wrapper handles transactions
    makes this impossible.
    """
    name = models.CharField(max_length=128)
    version = models.CharField(max_length=128)


class NamedAttribute(models.Model):
    """
    Model for adding generic named attributes
    to arbitrary other model instances.

    Example:
        class Foo(Model):
            attributes = generic.GenericRelation(NamedAttribute)
    """
    name = models.TextField()

    value = models.TextField()

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
        return ("dashboard_app.views.bundle_list", [self.pathname])

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

    def can_upload(self, user):
        """
        Return True if the user can upload bundles here
        """
        return self.is_anonymous or self.is_owned_by(user)


class GzipFileSystemStorage(FileSystemStorage):

    def _open(self, name, mode='rb'):
        full_path = self.path(name)
        gzip_file = gzip.GzipFile(full_path, mode)
        gzip_file.name = full_path
        return File(gzip_file)

    # This is a copy-paste-hack of FileSystemStorage._save
    def _save(self, name, content):
        full_path = self.path(name)

        directory = os.path.dirname(full_path)
        if not os.path.exists(directory):
            os.makedirs(directory)
        elif not os.path.isdir(directory):
            raise IOError("%s exists and is not a directory." % directory)

        # There's a potential race condition between get_available_name and
        # saving the file; it's possible that two threads might return the
        # same name, at which point all sorts of fun happens. So we need to
        # try to create the file, but if it already exists we have to go back
        # to get_available_name() and try again.

        while True:
            try:
                # This fun binary flag incantation makes os.open throw an
                # OSError if the file already exists before we open it.
                fd = os.open(full_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0))
                # This line, and the use of gz_file.write below, are the
                # changes from the original version of this.
                gz_file = gzip.GzipFile(fileobj=os.fdopen(fd, 'wb'))
                try:
                    locks.lock(fd, locks.LOCK_EX)
                    for chunk in content.chunks():
                        gz_file.write(chunk)
                finally:
                    locks.unlock(fd)
                    gz_file.close()
            except OSError, e:
                if e.errno == errno.EEXIST:
                    # Ooops, the file exists. We need a new file name.
                    name = self.get_available_name(name)
                    full_path = self.path(name)
                else:
                    raise
            else:
                # OK, the file save worked. Break out of the loop.
                break

        if settings.FILE_UPLOAD_PERMISSIONS is not None:
            os.chmod(full_path, settings.FILE_UPLOAD_PERMISSIONS)

        return name


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

    _raw_content = models.FileField(
            verbose_name = _(u"Content"),
            help_text = _(u"Document in Dashboard Bundle Format 1.0"),
            upload_to = 'bundles',
            null = True,
            db_column = 'content')

    _gz_content = models.FileField(
            verbose_name = _(u"Compressed content"),
            help_text = _(u"Compressed document in Dashboard Bundle Format 1.0"),
            upload_to = 'compressed-bundles',
            null = True,
            db_column = 'gz_content',
            storage = GzipFileSystemStorage())

    def _get_content(self):
        r = self._gz_content
        if not r:
            return self._raw_content
        else:
            return r

    content = property(_get_content)

    def compress(self):
        c = self._raw_content
        self._gz_content.save(c.name, c)
        c.delete()

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
        return _(u"Bundle {0}").format(self.content_sha1)

    class Meta:
        ordering = ['-uploaded_on']

    @models.permalink
    def get_absolute_url(self):
        return ("dashboard_app.views.bundle_detail", [self.bundle_stream.pathname, self.content_sha1])

    def get_permalink(self):
        return reverse("dashboard_app.views.redirect_to_bundle", args=[self.content_sha1])

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
            try:
                self.deserialization_error.delete()
            except BundleDeserializationError.DoesNotExist:
                pass
            self.is_deserialized = True
            self.save()
            bundle_was_deserialized.send_robust(sender=self, bundle=self)

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

    def get_sanitized_bundle(self):
        self.content.open()
        try:
            return SanitizedBundle(self.content)
        finally:
            self.content.close()

    def get_document_format(self):
        try:
            self.content.open('rb')
        except IOError:
            return "unknown"
        else:
            try:
                fmt, doc = DocumentIO.load(self.content)
                return fmt
            finally:
                self.content.close()

    def get_serialization_format(self):
        return "JSON"

    def get_content_size(self):
        try:
            return filesizeformat(self.content.size)
        except OSError:
            return "unknown"


class SanitizedBundle(object):

    def __init__(self, stream):
        try:
            self.bundle_json = simplejson.load(stream)
            self.deserialization_error = None
        except simplejson.JSONDeserializationError as ex:
            self.bundle_json = None
            self.deserialization_error = ex
        self.did_remove_attachments = False
        self._sanitize()

    def get_human_readable_json(self):
        return simplejson.dumps(self.bundle_json, indent=4)

    def _sanitize(self):
        for test_run in self.bundle_json.get("test_runs", []):
            attachments = test_run.get("attachments")
            if isinstance(attachments, list):
                for attachment in attachments:
                    attachment["content"] = None
                    self.did_remove_attachments = True
            elif isinstance(attachments, dict):
                for name in attachments:
                    attachments[name] = None
                    self.did_remove_attachments = True


class BundleDeserializationError(models.Model):
    """
    Model for representing errors encountered during bundle
    deserialization. There is one instance per bundle limit due to
    unique = True. There used to be a OneToOne field but it didn't work
    with databrowse application.

    The relevant logic for managing this is in the Bundle.deserialize()
    """

    bundle = models.OneToOneField(
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
        return ('dashboard_app.views.test_detail', [self.test_id])

    def count_results_without_test_case(self):
        return TestResult.objects.filter(
            test_run__test=self,
            test_case=None).count()

    def count_failures_without_test_case(self):
        return TestResult.objects.filter(
            test_run__test=self,
            test_case=None,
            result=TestResult.RESULT_FAIL).count()


class TestCase(models.Model):
    """
    Model for representing test cases.

    Test case is a unique component of a specific test.
    Test cases allow for relating to test results.
    """
    test = models.ForeignKey(
        Test,
        related_name='test_cases')

    test_case_id = models.TextField(
        help_text = _help_max_length(100),
        verbose_name = _("Test case ID"))

    name = models.TextField(
        blank = True,
        help_text = _help_max_length(100),
        verbose_name = _("Name"))

    units = models.TextField(
        blank = True,
        help_text = (_("""Units in which measurement value should be
                       interpreted in, for example <q>ms</q>, <q>MB/s</q> etc.
                       There is no semantical meaning inferred from the value of
                       this field, free form text is allowed. <br/>""")
                     + _help_max_length(100)),
        verbose_name = _("Units"))

    class Meta:
        unique_together = (('test', 'test_case_id'))

    def __unicode__(self):
        return self.name or self.test_case_id

    @models.permalink
    def get_absolute_url(self):
        return ("dashboard_app.test_case.details", [self.test.test_id, self.test_case_id])

    def count_failures(self):
        return self.test_results.filter(result=TestResult.RESULT_FAIL).count()


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

    # Tags

    tags = models.ManyToManyField(
        "Tag",
        blank=True,
        related_name='test_runs',
        verbose_name=_(u"Tags"))

    # Attachments

    attachments = generic.GenericRelation('Attachment')

    def __unicode__(self):
        return _(u"Test run {0}").format(self.analyzer_assigned_uuid)

    @models.permalink
    def get_absolute_url(self):
        return ("dashboard_app.views.test_run_detail",
                [self.bundle.bundle_stream.pathname,
                 self.bundle.content_sha1,
                 self.analyzer_assigned_uuid])

    def get_permalink(self):
        return reverse("dashboard_app.views.redirect_to_test_run", args=[self.analyzer_assigned_uuid])

    def get_board(self):
        """
        Return an associated Board device, if any.
        """
        try:
            return self.devices.filter(device_type="device.board").get()
        except HardwareDevice.DoesNotExist:
            pass
        except HardwareDevice.MultipleObjectsReturned:
            pass

    def get_results(self):
        """
        Get all results efficiently
        """
        return self.test_results.select_related(
            "test_case",  # explicit join on test_case which might be NULL
            "test_run",  # explicit join on test run, needed by all the get_absolute_url() methods
            "test_run__bundle",  # explicit join on bundle
            "test_run__bundle__bundle_stream",  # explicit join on bundle stream
        ).order_by("relative_index")  # sort as they showed up in the bundle

    def denormalize(self):
        try:
            self.denormalization
        except TestRunDenormalization.DoesNotExist:
            TestRunDenormalization.objects.create_from_test_run(self)

    def _get_summary_results(self, factor=3):
        stats = self.test_results.values('result').annotate(
            count=models.Count('result')).order_by()
        result = dict([
            (TestResult.RESULT_MAP[item['result']], item['count'])
            for item in stats])
        result['total'] = sum(result.values())
        result['total_multiplied'] = result['total'] * factor
        return result

    def get_summary_results(self):
        if not hasattr(self, '_cached_summary_results'):
            self._cached_summary_results = self._get_summary_results()
        return self._cached_summary_results

    class Meta:
        ordering = ['-import_assigned_date']


class TestRunDenormalization(models.Model):
    """
    Denormalized model for test run
    """

    test_run = models.OneToOneField(
        TestRun,
        primary_key=True,
        related_name="denormalization")

    count_pass = models.PositiveIntegerField(
        null=False,
        blank=False)

    count_fail = models.PositiveIntegerField(
        null=False,
        blank=False)

    count_skip = models.PositiveIntegerField(
        null=False,
        blank=False)

    count_unknown = models.PositiveIntegerField(
        null=False,
        blank=False)

    def count_all(self):
        return (self.count_pass + self.count_fail + self.count_skip +
                self.count_unknown)

    objects = TestRunDenormalizationManager()


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

    def is_test_run_attachment(self):
        if (self.content_type.app_label == 'dashboard_app' and
            self.content_type.model == 'testrun'):
            return True

    @property
    def test_run(self):
        if self.is_test_run_attachment():
            return self.content_object

    @models.permalink
    def get_absolute_url(self):
        if self.is_test_run_attachment():
            return ("dashboard_app.views.attachment_detail",
                    [self.test_run.bundle.bundle_stream.pathname,
                     self.test_run.bundle.content_sha1,
                     self.test_run.analyzer_assigned_uuid,
                     self.pk])


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

    @models.permalink
    def get_absolute_url(self):
        return ("dashboard_app.views.test_result_detail", [
            self.test_run.bundle.bundle_stream.pathname,
            self.test_run.bundle.content_sha1,
            self.test_run.analyzer_assigned_uuid,
            self.relative_index,
        ])

    def get_permalink(self):
        return reverse("dashboard_app.views.redirect_to_test_result",
                       args=[self.test_run.analyzer_assigned_uuid,
                             self.relative_index])

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


class DataView(RepositoryItem):
    """
    Data view, a container for SQL query and optional arguments
    """

    repository = DataViewRepository()

    def __init__(self, name, backend_queries, arguments, documentation, summary):
        self.name = name
        self.backend_queries = backend_queries
        self.arguments = arguments
        self.documentation = documentation
        self.summary = summary

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return "<DataView name=%r>" % (self.name,)

    @models.permalink
    def get_absolute_url(self):
        return ("dashboard_app.views.data_view_detail", [self.name])

    def _get_connection_backend_name(self, connection):
        backend = str(type(connection))
        if "sqlite" in backend:
            return "sqlite"
        elif "postgresql" in backend:
            return "postgresql"
        else:
            return ""

    def get_backend_specific_query(self, connection):
        """
        Return BackendSpecificQuery for the specified connection
        """
        sql_backend_name = self._get_connection_backend_name(connection)
        try:
            return self.backend_queries[sql_backend_name]
        except KeyError:
            return self.backend_queries.get(None, None)

    def lookup_argument(self, name):
        """
        Return Argument with the specified name

        Raises LookupError if the argument cannot be found
        """
        for argument in self.arguments:
            if argument.name == name:
                return argument
        raise LookupError(name)

    @classmethod
    def get_connection(cls):
        """
        Get the appropriate connection for data views
        """
        from django.db import connection, connections
        from django.db.utils import ConnectionDoesNotExist
        try:
            return connections['dataview']
        except ConnectionDoesNotExist:
            logging.warning("dataview-specific database connection not available, dataview query is NOT sandboxed")
            return connection  # NOTE: it's connection not connectionS (the default connection)

    def __call__(self, connection, **arguments):
        # Check if arguments have any bogus names
        valid_arg_names = frozenset([argument.name for argument in self.arguments])
        for arg_name in arguments:
            if arg_name not in valid_arg_names:
                raise TypeError("Data view %s has no argument %r" % (self.name, arg_name))
        # Get the SQL template for our database connection
        query = self.get_backend_specific_query(connection)
        if query is None:
            raise LookupError("Specified data view has no SQL implementation "
                              "for current database")
        # Replace SQL aruments with django placeholders (connection agnostic)
        template = query.sql_template
        template = template.replace("%", "%%")
        # template = template.replace("{", "{{").replace("}", "}}")
        sql = template.format(
            **dict([
                (arg_name, "%s")
                for arg_name in query.argument_list]))
        # Construct argument list using defaults for missing values
        sql_args = [
            arguments.get(arg_name, self.lookup_argument(arg_name).default)
            for arg_name in query.argument_list]
        with contextlib.closing(connection.cursor()) as cursor:
            # Execute the query with the specified arguments
            cursor.execute(sql, sql_args)
            # Get and return the results
            rows = cursor.fetchall()
            columns = cursor.description
            return rows, columns


class DataReport(RepositoryItem):
    """
    Data reports are small snippets of xml that define
    a limited django template.
    """

    repository = DataReportRepository()

    def __init__(self, **kwargs):
        self._html = None
        self._data = kwargs

    def __unicode__(self):
        return self.title

    def __repr__(self):
        return "<DataReport name=%r>" % (self.name,)

    @models.permalink
    def get_absolute_url(self):
        return ("dashboard_app.views.report_detail", [self.name])

    def _get_raw_html(self):
        pathname = os.path.join(self.base_path, self.path)
        try:
            with open(pathname) as stream:
                return stream.read()
        except (IOError, OSError) as ex:
            logging.error("Unable to load DataReport HTML file from %r: %s", pathname, ex)
            return ""

    def _get_html_template(self):
        return Template(self._get_raw_html())

    def _get_html_template_context(self):
        from django.conf import settings
        return Context({
            "API_URL": reverse("dashboard_app.views.dashboard_xml_rpc_handler"),
            "STATIC_URL": settings.STATIC_URL
        })

    def get_html(self):
        from django.conf import settings
        DEBUG = getattr(settings, "DEBUG", False)
        if self._html is None or DEBUG is True:
            template = self._get_html_template()
            context = self._get_html_template_context()
            self._html = template.render(context)
        return self._html

    @property
    def title(self):
        return self._data['title']

    @property
    def path(self):
        return self._data['path']

    @property
    def name(self):
        return self._data['name']

    @property
    def bug_report_url(self):
        return self._data.get('bug_report_url')

    @property
    def author(self):
        return self._data.get('author')

    @property
    def front_page(self):
        return self._data['front_page']


class Tag(models.Model):
    """
    Tag used for marking test runs.
    """
    name = models.SlugField(
        verbose_name=_(u"Tag"),
        max_length=256,
        db_index=True,
        unique=True)

    def __unicode__(self):
        return self.name


class TestingEffort(models.Model):
    """
    A collaborative effort to test something.

    Uses tags to associate with test runs.
    """
    project = models.ForeignKey(
        Project,
        related_name="testing_efforts")

    name = models.CharField(
        verbose_name=_(u"Name"),
        max_length=100)

    description = models.TextField(
        verbose_name=_(u"Description"),
        help_text=_(u"Description of this testing effort"))

    tags = models.ManyToManyField(
        Tag,
        verbose_name=_(u"Tags"),
        related_name="testing_efforts")

    def __unicode__(self):
        return self.name

    @models.permalink
    def get_absolute_url(self):
        return ("dashboard_app.views.testing_effort_detail", [self.pk])

    def get_test_runs(self):
        return TestRun.objects.order_by(
        ).filter(
            tags__in=self.tags.all())


class ImageAttribute(models.Model):

    name = models.CharField(max_length=1024)
    value = models.CharField(max_length=1024)

    image = models.ForeignKey("Image", related_name="required_attributes")

    def __unicode__(self):
        return '%s = %s' % (self.name, self.value)

class Image(models.Model):

    name = models.SlugField(max_length=1024, unique=True)

    build_number_attribute = models.CharField(max_length=1024)

    bundle_streams = models.ManyToManyField(BundleStream)

    uploaded_by = models.ForeignKey(User, null=True, blank=True)

    def __unicode__(self):
        return self.name

    def _get_bundles(self, user):
        accessible_bundles = BundleStream.objects.accessible_by_principal(
            user)
        args = [models.Q(bundle_stream__in=accessible_bundles)]
        if self.bundle_streams.exists():
            args += [models.Q(bundle_stream__in=self.bundle_streams.all())]
        if self.uploaded_by:
            args += [models.Q(uploaded_by=self.uploaded_by)]
        bundles = Bundle.objects.filter(*args)

        # This is a little tricky.  We want to AND together the conditions
        # that the attribute matches, but with the Django ORM we can only join
        # the attribute table once per query so we put each condition in a
        # nested query, so for example instead of something like this:
        #
        # select * from bundle
        #  where <bundle.testrun.name is vexpress>
        #    and <bundle.testrun.image_type = 'desktop';
        #
        # we generate this:
        #
        # select * from bundle
        #  where <bundle.testrun.name is vexpress>
        #    and bundle.id in
        #      (select * from bundle
        #       where <bundle.testrun.image_type = 'desktop');
        #
        # (additionally, we only consider the lava testrun to avoid returning
        # bundles repeatedly).

        for attr in self.required_attributes.all():
            bundles = Bundle.objects.filter(
                id__in=bundles.values_list('id'),
                test_runs__test__test_id='lava',
                test_runs__attributes__name=attr.name,
                test_runs__attributes__value=attr.value)

        return bundles

    def get_bundles(self, user):
        return Bundle.objects.filter(
            id__in=self._get_bundles(user).values('id'),
            test_runs__test__test_id='lava',
            test_runs__attributes__name=self.build_number_attribute)

    def get_latest_bundles(self, user, count):
        return Bundle.objects.filter(
            id__in=self._get_bundles(user).values('id'),
            test_runs__test__test_id='lava',
            test_runs__attributes__name=self.build_number_attribute).extra(
            select={
                'build_number': 'convert_to_integer("dashboard_app_namedattribute"."value")',
                }).extra(
            order_by=['-build_number'],
            )[:count]

    @models.permalink
    def get_absolute_url(self):
        return ("dashboard_app.views.image_report_detail", (), dict(name=self.name))


class ImageSet(models.Model):

    name = models.CharField(max_length=1024, unique=True)

    images = models.ManyToManyField(Image, help_text="This field is now obsolete")

    filters = models.ManyToManyField("TestRunFilter")

    def __unicode__(self):
        return self.name


class LaunchpadBug(models.Model):

    bug_id = models.PositiveIntegerField(unique=True)

    test_runs = models.ManyToManyField(TestRun, related_name='launchpad_bugs')

    def __unicode__(self):
        return unicode(self.bug_id)

@receiver(post_delete)
def file_cleanup(sender, instance, **kwargs):
    """
    Signal receiver used for remove FieldFile attachments when removing
    objects (Bundle and Attachment) from the database.
    """
    if instance is None or sender not in (Bundle, Attachment):
        return
    meta = sender._meta

    for field_name in meta.get_all_field_names():

        # object that represents the metadata of the field
        try:
            field_meta = meta.get_field(field_name)
        except FieldDoesNotExist:
            continue

        # we just want the FileField's, not all the fields
        if not isinstance(field_meta, models.FileField):
            continue

        # the field itself is a FieldFile instance, proxied by FileField
        field = getattr(instance, field_name)

        # the 'path' attribute contains the name of the file we need
        if hasattr(field, 'path') and os.path.exists(field.path):
            field.storage.delete(field.path)


class FilterMatch(object):
    """A non-database object that represents the way a filter matches a test_run.

    Returned by TestRunFilter.matches_against_bundle and
    TestRunFilter.get_test_runs.
    """

    filter = None
    tag = None # either a date (bundle__uploaded_on) or a build number
    test_runs = None
    specific_results = None # Will stay none unless filter specifies a test case
    pass_count = None # Only filled out for filters that dont specify a test
    result_code = None # Ditto

    def _format_test_result(self, result):
        prefix = result.test_case.test.test_id + ':' + result.test_case.test_case_id + ' '
        if result.test_case.units:
            return prefix + '%s%s' % (result.measurement, result.units)
        else:
            return prefix + result.RESULT_MAP[result.result]

    def _format_test_run(self, tr):
        return "%s %s pass / %s total" % (
            tr.test.test_id,
            tr.denormalization.count_pass,
            tr.denormalization.count_all())

    def _format_many_test_runs(self):
        return "%s pass / %s total" % (self.pass_count, self.result_count)

    def format_for_mail(self):
        r = [' ~%s/%s ' % (self.filter.owner.username, self.filter.name)]
        if not self.filter_data['tests']:
            r.append(self._format_many_test_runs())
        else:
            for test in self.filter_data['tests']:
                if not test.all_case_ids():
                    for tr in self.test_runs:
                        if tr.test == test.test:
                            r.append('\n    ')
                            r.append(self._format_test_run(tr))
                for case_id in test.all_case_ids():
                    for result in self.specific_results:
                        if result.test_case.id == case_id:
                            r.append('\n    ')
                            r.append(self._format_test_result(result))
        r.append('\n')
        return ''.join(r)


class MatchMakingQuerySet(object):
    """Wrap a QuerySet and construct FilterMatchs from what the wrapped query
    set returns.

    Just enough of the QuerySet API to work with DataTable (i.e. ordering and
    slicing)."""

    model = TestRun

    def __init__(self, queryset, filter_data):
        self.queryset = queryset
        self.filter_data = filter_data
        if filter_data['build_number_attribute']:
            self.key = 'build_number'
            self.key_name = 'Build'
        else:
            self.key = 'bundle__uploaded_on'
            self.key_name = 'Uploaded On'

    def _makeMatches(self, data):
        test_run_ids = set()
        for datum in data:
            test_run_ids.update(datum['id__arrayagg'])
        r = []
        trs = TestRun.objects.filter(id__in=test_run_ids).select_related(
            'denormalization', 'bundle', 'bundle__bundle_stream', 'test')
        trs_by_id = {}
        for tr in trs:
            trs_by_id[tr.id] = tr
        case_ids = set()
        for t in self.filter_data['tests']:
            case_ids.update(t.all_case_ids())
        if case_ids:
            result_ids_by_tr_id = {}
            results_by_tr_id = {}
            values = TestResult.objects.filter(
                test_case__id__in=case_ids,
                test_run__id__in=test_run_ids).values_list(
                'test_run__id', 'id')
            result_ids = set()
            for v in values:
                result_ids_by_tr_id.setdefault(v[0], []).append(v[1])
                result_ids.add(v[1])

            results_by_id = {}
            for result in TestResult.objects.filter(
                id__in=list(result_ids)).select_related(
                'test', 'test_case', 'test_run__bundle__bundle_stream'):
                results_by_id[result.id] = result

            for tr_id, result_ids in result_ids_by_tr_id.items():
                rs = results_by_tr_id[tr_id] = []
                for result_id in result_ids:
                    rs.append(results_by_id[result_id])
        for datum in data:
            trs = []
            for id in set(datum['id__arrayagg']):
                trs.append(trs_by_id[id])
            match = FilterMatch()
            match.test_runs = trs
            match.filter_data = self.filter_data
            match.tag = datum[self.key]
            if case_ids:
                match.specific_results = []
                for id in set(datum['id__arrayagg']):
                    match.specific_results.extend(results_by_tr_id.get(id, []))
            else:
                match.pass_count = sum(tr.denormalization.count_pass for tr in trs)
                match.result_count = sum(tr.denormalization.count_all() for tr in trs)
            r.append(match)
        return iter(r)

    def _wrap(self, queryset, **kw):
        return self.__class__(queryset, self.filter_data, **kw)

    def order_by(self, *args):
        # the generic tables code calls this even when it shouldn't...
        return self

    def count(self):
        return self.queryset.count()

    def __getitem__(self, item):
        return self._wrap(self.queryset[item])

    def __iter__(self):
        data = list(self.queryset)
        return self._makeMatches(data)


class TestRunFilterAttribute(models.Model):

    name = models.CharField(max_length=1024)
    value = models.CharField(max_length=1024)

    filter = models.ForeignKey("TestRunFilter", related_name="attributes")

    def __unicode__(self):
        return '%s = %s' % (self.name, self.value)


class TestRunFilterTest(models.Model):

    test = models.ForeignKey(Test, related_name="+")
    filter = models.ForeignKey("TestRunFilter", related_name="tests")
    index = models.PositiveIntegerField(
        help_text = _(u"The index of this test in the filter"))

    def all_case_ids(self):
        return self.cases.all().order_by('index').values_list('test_case__id', flat=True)

    def all_case_names(self):
        return self.cases.all().order_by('index').values_list('test_case__test_case_id', flat=True)

    def __unicode__(self):
        return unicode(self.test)


class TestRunFilterTestCase(models.Model):

    test_case = models.ForeignKey(TestCase, related_name="+")
    test = models.ForeignKey(TestRunFilterTest, related_name="cases")
    index = models.PositiveIntegerField(
        help_text = _(u"The index of this case in the test"))

    def __unicode__(self):
        return unicode(self.test_case)


class SQLArrayAgg(SQLAggregate):
    sql_function = 'array_agg'


class ArrayAgg(models.Aggregate):
    name = 'ArrayAgg'
    def add_to_query(self, query, alias, col, source, is_summary):
        aggregate = SQLArrayAgg(
            col, source=source, is_summary=is_summary, **self.extra)
        # For way more detail than you want about what this next line is for,
        # see
        # http://voices.canonical.com/michael.hudson/2012/09/02/using-postgres-array_agg-from-django/
        aggregate.field = models.DecimalField() # vomit
        query.aggregates[alias] = aggregate


class TestRunFilter(models.Model):

    owner = models.ForeignKey(User)

    name = models.SlugField(
        max_length=1024,
        help_text=("The <b>name</b> of a filter is used to refer to it in "
                   "the web UI and in email notifications triggered by this "
                   "filter."))
    class Meta:
        unique_together = (('owner', 'name'))

    bundle_streams = models.ManyToManyField(BundleStream)
    bundle_streams.help_text = 'A filter only matches tests within the given <b>bundle streams</b>.'

    public = models.BooleanField(
        default=False, help_text="Whether other users can see this filter.")

    build_number_attribute = models.CharField(
        max_length=1024, blank=True, null=True,
        help_text="For some filters, there is a natural <b>build number</b>.  If you specify the name of the attribute that contains the build number here, the results of the filter will be grouped and ordered by this build number.")

    uploaded_by = models.ForeignKey(
        User, null=True, blank=True, related_name='+',
        help_text="Only consider bundles uploaded by this user")

    enable_as_image = models.BooleanField(default=False)

    @property
    def summary_data(self):
        return {
            'bundle_streams': self.bundle_streams.all(),
            'attributes': self.attributes.all().values_list('name', 'value'),
            'tests': self.tests.all().prefetch_related('cases'),
            'build_number_attribute': self.build_number_attribute,
            }

    def __unicode__(self):
        return "<TestRunFilter ~%s/%s>" % (self.owner.username, self.name)

    # given filter:
    # select from testrun
    #  where testrun.bundle in filter.bundle_streams ^ accessible_bundles 
    #    and testrun has attribute with key = key1 and value = value1
    #    and testrun has attribute with key = key2 and value = value2
    #    and               ...
    #    and testrun has attribute with key = keyN and value = valueN
    #    and testrun has any of the tests/testcases requested

    def get_test_runs_impl(self, user, bundle_streams, attributes, tests):
        accessible_bundle_streams = BundleStream.objects.accessible_by_principal(
            user)
        bs_ids = [bs.id for bs in set(accessible_bundle_streams) & set(bundle_streams)]
        conditions = [models.Q(bundle__bundle_stream__id__in=bs_ids)]

        content_type_id = ContentType.objects.get_for_model(TestRun).id

        for (name, value) in attributes:
            # We punch through the generic relation abstraction here for 100x
            # better performance.
            conditions.append(
                models.Q(id__in=NamedAttribute.objects.filter(
                    name=name, value=value, content_type_id=content_type_id
                    ).values('object_id')))

        test_condition = None
        for test in tests:
            cases = list(test.all_case_ids())
            if cases:
                q = models.Q(
                    test__id=test.test.id,
                    test_results__test_case__id__in=cases)
            else:
                q = models.Q(test__id=test.test.id)
            if test_condition:
                test_condition = test_condition | q
            else:
                test_condition = q
        if test_condition:
            conditions.append(test_condition)

        if self.uploaded_by:
            conditions.append(models.Q(bundle__uploaded_by=self.uploaded_by))

        testruns = TestRun.objects.filter(*conditions)

        if self.build_number_attribute:
            testruns = testruns.filter(
                attributes__name=self.build_number_attribute).extra(
                select={
                    'build_number': 'convert_to_integer("dashboard_app_namedattribute"."value")',
                    },
                where=['convert_to_integer("dashboard_app_namedattribute"."value") IS NOT NULL']).extra(
                order_by=['-build_number'],
                ).values('build_number').annotate(ArrayAgg('id'))
        else:
            testruns = testruns.order_by('-bundle__uploaded_on').values(
                'bundle__uploaded_on').annotate(ArrayAgg('id'))

        filter_data = {
            'bundle_streams': bundle_streams,
            'attributes': attributes,
            'tests': tests,
            'build_number_attribute': self.build_number_attribute,
            }

        return MatchMakingQuerySet(testruns, filter_data)

    # given bundle:
    # select from filter
    #  where bundle.bundle_stream in filter.bundle_streams
    #    and filter.test in (select test from bundle.test_runs)
    #    and all the attributes on the filter are on a testrun in the bundle
    #       = the minimum over testrun (the number of attributes on the filter that are not on the testrun) is 0
    #    and (filter.test_case is null
    #         or filter.test_case in select test_case from bundle.test_runs.test_results.test_cases)

    @classmethod
    def matches_against_bundle(self, bundle):
        bundle_filters = bundle.bundle_stream.testrunfilter_set.all()
        attribute_filters = list(bundle_filters.extra(
            where=[
            """(select min((select count(*)
                              from dashboard_app_testrunfilterattribute
                             where filter_id = dashboard_app_testrunfilter.id
                               and (name, value) not in (select name, value
                                                           from dashboard_app_namedattribute
                                  where content_type_id = (
                                          select django_content_type.id from django_content_type
                                          where app_label = 'dashboard_app' and model='testrun')
                                 and object_id = dashboard_app_testrun.id)))
            from dashboard_app_testrun where dashboard_app_testrun.bundle_id = %s) = 0""" % bundle.id],
            ))
        no_test_filters = []#list(attribute_filters.annotate(models.Count('tests')).filter(tests__count=0))
        no_test_case_filters = list(
            TestRunFilter.objects.filter(
                id__in=TestRunFilterTest.objects.filter(
                    filter__in=attribute_filters, test__in=bundle.test_runs.all().values('test_id')).annotate(
                    models.Count('cases')).filter(cases__count=0).values('filter__id'),
                ))
        tcf = TestRunFilter.objects.filter(
            id__in=TestRunFilterTest.objects.filter(
                filter__in=attribute_filters,
                cases__test_case__id__in=bundle.test_runs.all().values('test_results__test_case__id')
                ).values('filter__id')
            )
        test_case_filters = list(tcf)

        filters = set(test_case_filters + no_test_case_filters + no_test_filters)
        matches = []
        bundle_with_counts = Bundle.objects.annotate(
            pass_count=models.Sum('test_runs__denormalization__count_pass'),
            unknown_count=models.Sum('test_runs__denormalization__count_unknown'),
            skip_count=models.Sum('test_runs__denormalization__count_skip'),
            fail_count=models.Sum('test_runs__denormalization__count_fail')).get(
            id=bundle.id)
        for filter in filters:
            match = FilterMatch()
            match.filter = filter
            match.filter_data = filter.summary_data
            match.test_runs = list(bundle.test_runs.all())
            match.specific_results = list(
                TestResult.objects.filter(
                    test_case__id__in=filter.tests.all().values('cases__test_case__id'),
                    test_run__bundle=bundle))
            b = bundle_with_counts
            match.result_count = b.unknown_count + b.skip_count + b.pass_count + b.fail_count
            match.pass_count = bundle_with_counts.pass_count
            matches.append(match)
        return matches

    def get_test_runs(self, user):
        return self.get_test_runs_impl(
            user,
            self.bundle_streams.all(),
            self.attributes.values_list('name', 'value'),
            self.tests.all())

    @models.permalink
    def get_absolute_url(self):
        return (
            "dashboard_app.views.filter_detail",
            [self.owner.username, self.name])


class TestRunFilterSubscription(models.Model):

    user = models.ForeignKey(User)

    filter = models.ForeignKey(TestRunFilter)

    class Meta:
        unique_together = (('user', 'filter'))

    NOTIFICATION_FAILURE, NOTIFICATION_ALWAYS = range(2)

    NOTIFICATION_CHOICES = (
        (NOTIFICATION_FAILURE, "Only when failed"),
        (NOTIFICATION_ALWAYS, "Always"))

    level = models.IntegerField(
        default=NOTIFICATION_FAILURE, choices=NOTIFICATION_CHOICES,
        help_text=("You can choose to be <b>notified by email</b>:<ul><li>whenever a test "
                   "that matches the criteria of this filter is executed"
                   "</li><li>only when a test that matches the criteria of this filter fails</ul>"))

    @classmethod
    def recipients_for_bundle(cls, bundle):
        matches = TestRunFilter.matches_against_bundle(bundle)
        matches_by_filter_id = {}
        for match in matches:
            matches_by_filter_id[match.filter.id] = match
        args = [models.Q(filter_id__in=list(matches_by_filter_id))]
        bs = bundle.bundle_stream
        if not bs.is_public:
            if bs.group:
                args.append(models.Q(user__in=bs.group.user_set.all()))
            else:
                args.append(models.Q(user=bs.user))
        subscriptions = TestRunFilterSubscription.objects.filter(*args)
        recipients = {}
        for sub in subscriptions:
            match = matches_by_filter_id[sub.filter.id]
            if sub.level == cls.NOTIFICATION_FAILURE:
                failure_found = False
                if not match.filter_data['tests']:
                    failure_found = match.pass_count != match.result_count
                else:
                    for t in match.filter_data['tests']:
                        if not t.all_case_ids():
                            for tr in match.test_runs:
                                if tr.test == t.test:
                                    if tr.denormalization.count_pass != tr.denormalization.count_all():
                                        failure_found = True
                                        break
                        if failure_found:
                            break
                if not failure_found:
                    for r in match.specific_results:
                        if r.result != TestResult.RESULT_PASS:
                            failure_found = True
                            break
                if not failure_found:
                    continue
            recipients.setdefault(sub.user, []).append(match)
        return recipients


def send_bundle_notifications(sender, bundle, **kwargs):
    recipients = TestRunFilterSubscription.recipients_for_bundle(bundle)
    domain = '???'
    try:
        site = Site.objects.get_current()
    except (Site.DoesNotExist, ImproperlyConfigured):
        pass
    else:
        domain = site.domain
    url_prefix = 'http://%s' % domain
    for user, matches in recipients.items():
        data = {'bundle': bundle, 'user': user, 'matches': matches, 'url_prefix': url_prefix}
        mail = render_to_string(
            'dashboard_app/filter_subscription_mail.txt',
            data)
        filter_names = ', '.join(match.filter.name for match in matches)
        send_mail(
            "LAVA result notification: " + filter_names, mail,
            settings.SERVER_EMAIL, [user.email])


bundle_was_deserialized.connect(send_bundle_notifications)
