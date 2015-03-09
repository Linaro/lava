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

import ast
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
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.exceptions import (
    ImproperlyConfigured,
    ValidationError,
    PermissionDenied
)
from django.core.files import locks, File
from django.core.files.storage import FileSystemStorage
from django.core.mail import send_mail
from django.core.urlresolvers import reverse
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator
)
from django.db import models, connection, IntegrityError
from django.db.models.fields import FieldDoesNotExist
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.template import Template, Context
from django.template.defaultfilters import filesizeformat, slugify
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ungettext_lazy
from django.db.utils import DatabaseError
from django_restricted_resource.models import RestrictedResource
from linaro_dashboard_bundle.io import DocumentIO

from dashboard_app.helpers import BundleDeserializer
from dashboard_app.managers import BundleManager, TestRunDenormalizationManager
from dashboard_app.signals import bundle_was_deserialized


def _help_max_length(max_length):
    return ungettext_lazy(
        u"Maximum length: {0} character",
        u"Maximum length: {0} characters",
        max_length).format(max_length)


class SoftwarePackage(models.Model):
    """
    Model for software packages.
    """
    name = models.CharField(
        max_length=128,
        verbose_name=_(u"Package name"),
        help_text=_help_max_length(128))

    version = models.CharField(
        max_length=128,
        verbose_name=_(u"Package version"),
        help_text=_help_max_length(128))

    class Meta:
        unique_together = (('name', 'version'))

    def __unicode__(self):
        return _(u"{name} {version}").format(
            name=self.name,
            version=self.version)

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
            name=self.name,
            value=self.value)

    class Meta:
        unique_together = (('object_id', 'name'))


class HardwareDevice(models.Model):
    """
    Model for hardware devices

    All devices are simplified into an instance of pre-defined class
    with arbitrary key-value attributes.
    """
    device_type = models.CharField(
        choices=(
            (u"device.cpu", _(u"CPU")),
            (u"device.mem", _(u"Memory")),
            (u"device.usb", _(u"USB device")),
            (u"device.pci", _(u"PCI device")),
            (u"device.board", _(u"Board/Motherboard"))),
        help_text=_(u"One of pre-defined device types"),
        max_length=32,
        verbose_name=_(u"Device Type"),
    )

    description = models.CharField(
        help_text=_(u"Human readable device summary.") + " " + _help_max_length(256),
        max_length=256,
        verbose_name=_(u"Description"),
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
        blank=True,
        help_text=(_(u"Name that you will use when uploading bundles.")
                   + " " + _help_max_length(64)),
        max_length=64,
        verbose_name=_(u"Slug"),
    )

    name = models.CharField(
        blank=True,
        help_text=_help_max_length(64),
        max_length=64,
        verbose_name=_(u"Name"),
    )

    pathname = models.CharField(
        max_length=128,
        editable=False,
        unique=True,
    )

    is_anonymous = models.BooleanField(default=False)

    def __unicode__(self):
        return self.pathname

    @models.permalink
    def get_absolute_url(self):
        return ("dashboard_app.views.bundle_list", [self.pathname])

    def get_test_run_count(self):
        return TestRun.objects.filter(bundle__bundle_stream=self).count()

    def clean(self):
        # default values are None if not specified, assert False.
        if not self.is_anonymous:
            self.is_anonymous = False
        if not self.is_public:
            self.is_public = False
        if self.is_anonymous and not self.is_public:
            raise ValidationError(
                'Anonymous streams must be public')
        return super(BundleStream, self).clean()

    @classmethod
    def create_from_pathname(cls, pathname, user=None, name=None):
        """
        Create new bundle stream from pathname.

        Checks for various user/group permissions.
        Raises ValueError if the pathname is not well formed.
        Raises PermissionDenied if user cannot create this stream or does not
        belong to the right group.
        Raises IntegrityError if bundle stream already exists.

        :param pathname: bundle stream pathname.
        :param name: optional name of the bundle stream.
        :param user: user which is trying to create a bundle.
        """
        if name is None:
            name = ""

        try:
            user_name, group_name, slug, is_public, is_anonymous = BundleStream.parse_pathname(pathname)
        except ValueError:
            raise

        # Start with those to simplify the logic below
        owner = None
        group = None
        if is_anonymous is False:
            if user is not None:
                if user_name is not None:
                    if not user.is_superuser:
                        if user_name != user.username:
                            raise PermissionDenied("Only user {user!r} could create this stream".format(user=user_name))
                    owner = user  # map to real user object
                elif group_name is not None:
                    try:
                        if user.is_superuser:
                            group = Group.objects.get(name=group_name)
                        else:
                            group = user.groups.get(name=group_name)
                    except Group.DoesNotExist:
                        raise PermissionDenied("Only a member of group {group!r} could create this stream".format(group=group_name))
            else:
                raise PermissionDenied(
                    "Only anonymous streams can be constructed.")
        else:
            if user is not None:
                owner = user
            else:
                # Hacky but will suffice for now
                owner = User.objects.get_or_create(
                    username="anonymous-owner")[0]
        try:
            bundle_stream = BundleStream.objects.create(
                user=owner,
                group=group,
                slug=slug,
                is_public=is_public,
                is_anonymous=is_anonymous,
                name=name)

        except IntegrityError:
            raise
        else:
            return bundle_stream

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
        if not pathname.endswith('/'):
            pathname = pathname + '/'
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
        return self.is_anonymous or self.is_owned_by(user) or user.is_superuser


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
    bundle_stream = models.ForeignKey(
        BundleStream,
        verbose_name=_(u"Stream"),
        related_name='bundles')

    uploaded_by = models.ForeignKey(
        User,
        verbose_name=_(u"Uploaded by"),
        help_text=_(u"The user who submitted this bundle"),
        related_name='uploaded_bundles',
        null=True,
        blank=True)

    uploaded_on = models.DateTimeField(
        verbose_name=_(u"Uploaded on"),
        editable=False,
        default=datetime.datetime.utcnow)

    is_deserialized = models.BooleanField(
        verbose_name=_(u"Is deserialized"),
        help_text=_(u"Set when document has been analyzed and loaded"
                    " into the database"),
        editable=False,
        default=False)

    _raw_content = models.FileField(
        verbose_name=_(u"Content"),
        help_text=_(u"Document in Dashboard Bundle Format 1.0"),
        upload_to='bundles',
        null=True,
        db_column='content')

    _gz_content = models.FileField(
        verbose_name=_(u"Compressed content"),
        help_text=_(u"Compressed document in Dashboard Bundle Format 1.0"),
        upload_to='compressed-bundles',
        null=True,
        db_column='gz_content',
        storage=GzipFileSystemStorage())

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
        editable=False,
        max_length=40,
        null=True,
        unique=True)

    content_filename = models.CharField(
        verbose_name=_(u"Content file name"),
        help_text=_(u"Name of the originally uploaded bundle"),
        max_length=256)

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
        if not self.is_deserialized:
            self.is_deserialized = False
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
                test_run__bundle=self).values('result').annotate(count=models.Count('result'))
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
            except Exception:
                return "unknown"
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
        except TypeError as ex:
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
        primary_key=True,
        unique=True,
        related_name='deserialization_error'
    )

    error_message = models.CharField(
        max_length=1024
    )

    traceback = models.TextField(
        max_length=1 << 15,
    )

    def __unicode__(self):
        return self.error_message


class Test(models.Model):
    """
    Model for representing tests.

    Test is a collection of individual test cases.
    """
    test_id = models.CharField(
        max_length=1024,
        verbose_name=_("Test ID"),
        unique=True)

    name = models.CharField(
        blank=True,
        max_length=1024,
        verbose_name=_(u"Name"))

    def __unicode__(self):
        return self.name or self.test_id

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
        verbose_name=_("Test case ID"))

    name = models.TextField(
        blank=True,
        help_text=_help_max_length(100),
        verbose_name=_("Name"))

    units = models.TextField(
        blank=True,
        help_text=(_("""Units in which measurement value should be
                     interpreted in, for example <q>ms</q>, <q>MB/s</q> etc.
                     There is no semantical meaning inferred from the value of
                     this field, free form text is allowed. <br/>""")
                   + _help_max_length(100)),
        verbose_name=_("Units"))

    class Meta:
        unique_together = (('test', 'test_case_id'))

    def __unicode__(self):
        return self.name or self.test_case_id

    def count_failures(self):
        return self.test_results.filter(result=TestResult.RESULT_FAIL).count()


class TestDefinition(models.Model):
    """
    Model for representing test definitions.

    Test Definition are in YAML format.
    """
    LOCATION_CHOICES = (
        ('LOCAL', 'Local'),
        ('URL', 'URL'),
        ('GIT', 'GIT Repo'),
        ('BZR', 'BZR Repo'),
    )

    name = models.CharField(
        max_length=512,
        verbose_name=_("Name"),
        unique=True,
        help_text=_help_max_length(512))

    version = models.CharField(
        max_length=256,
        verbose_name=_("Version"),
        help_text=_help_max_length(256))

    description = models.TextField(
        verbose_name=_("Description"))

    format = models.CharField(
        max_length=128,
        verbose_name=_("Format"),
        help_text=_help_max_length(128))

    location = models.CharField(
        max_length=64,
        verbose_name=_("Location"),
        choices=LOCATION_CHOICES,
        default='LOCAL')

    url = models.CharField(
        verbose_name=_(u"URL"),
        max_length=1024,
        blank=False,
        help_text=_help_max_length(1024))

    environment = models.CharField(
        max_length=256,
        verbose_name=_("Environment"),
        help_text=_help_max_length(256))

    target_os = models.CharField(
        max_length=512,
        verbose_name=_("Operating Systems"),
        help_text=_help_max_length(512))

    target_dev_types = models.CharField(
        max_length=512,
        verbose_name=_("Device types"),
        help_text=_help_max_length(512))

    content = models.FileField(
        verbose_name=_(u"Upload Test Definition"),
        help_text=_(u"Test definition file"),
        upload_to='testdef',
        blank=True,
        null=True)

    mime_type = models.CharField(
        verbose_name=_(u"MIME type"),
        default='text/plain',
        max_length=64,
        help_text=_help_max_length(64))

    def __unicode__(self):
        return self.name


class SoftwareSource(models.Model):
    """
    Model for representing source reference of a particular project
    """

    project_name = models.CharField(
        max_length=32,
        help_text=_help_max_length(32),
        verbose_name=_(u"Project Name"),
    )
    branch_url = models.CharField(
        max_length=256,
        help_text=_help_max_length(256),
        verbose_name=_(u"Branch URL"),
    )
    branch_vcs = models.CharField(
        max_length=10,
        help_text=_help_max_length(10),
        verbose_name=_(u"Branch VCS"),
    )
    branch_revision = models.CharField(
        max_length=128,
        help_text=_help_max_length(128),
        verbose_name=_(u"Branch Revision")
    )
    commit_timestamp = models.DateTimeField(
        blank=True,
        null=True,
        help_text=_(u"Date and time of the commit (optional)"),
        verbose_name=_(u"Commit Timestamp")
    )
    default_params = models.CharField(
        max_length=1024,
        blank=True,
        null=True,
        help_text="Default parameters for lava-test-shell.",
        verbose_name=_(u"Default parameters")
    )
    test_params = models.CharField(
        max_length=1024,
        blank=True,
        null=True,
        help_text="Runtime test parameters for lava-test-shell.",
        verbose_name=_(u"Test parameters")
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
        related_name='test_runs',
    )

    test = models.ForeignKey(
        Test,
        related_name='test_runs',
    )

    analyzer_assigned_uuid = models.CharField(
        help_text=_(u"You can use uuid.uuid1() to generate a value"),
        max_length=36,
        unique=True,
        verbose_name=_(u"Analyzer assigned UUID"),
    )

    analyzer_assigned_date = models.DateTimeField(
        verbose_name=_(u"Analyzer assigned date"),
        help_text=_(u"Time stamp when the log was processed by the log"
                    " analyzer"),
    )

    import_assigned_date = models.DateTimeField(
        verbose_name=_(u"Import assigned date"),
        help_text=_(u"Time stamp when the bundle was imported"),
        auto_now_add=True,
    )

    time_check_performed = models.BooleanField(
        verbose_name=_(u"Time check performed"),
        help_text=_(u"Indicator on wether timestamps in the log file (and any "
                    "data derived from them) should be trusted.<br/>"
                    "Many pre-production or development devices do not "
                    "have a battery-powered RTC and it's not common for "
                    "development images not to synchronize time with "
                    "internet time servers.<br/>"
                    "This field allows us to track tests results that "
                    "<em>certainly</em> have correct time if we ever end up "
                    "with lots of tests results from 1972"),
        default=False)

    microseconds = models.BigIntegerField(
        blank=True,
        null=True
    )

    # Software Context

    sw_image_desc = models.CharField(
        blank=True,
        max_length=100,
        verbose_name=_(u"Operating System Image"),
    )

    packages = models.ManyToManyField(
        SoftwarePackage,
        blank=True,
        related_name='test_runs',
        verbose_name=_(u"Software packages"),
    )

    sources = models.ManyToManyField(
        SoftwareSource,
        blank=True,
        related_name='test_runs',
        verbose_name=_(u"Software sources"),
    )

    # Hardware Context

    devices = models.ManyToManyField(
        HardwareDevice,
        blank=True,
        related_name='test_runs',
        verbose_name=_(u"Hardware devices"),
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
        :param result: used for filtering the result which we want.
                       It will return all reaults if the parameter 'result' is not in TestResult.RESULT_MAP.
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

    # test_duration property

    def _get_test_duration(self):
        if self.microseconds is None:
            return None
        else:
            return datetime.timedelta(microseconds=self.microseconds)

    def _set_test_duration(self, duration):
        if duration is None:
            self.microseconds = None
        else:
            if not isinstance(duration, datetime.timedelta):
                raise TypeError("duration must be a datetime.timedelta() instance")
            self.microseconds = (
                duration.microseconds +
                (duration.seconds * 10 ** 6) +
                (duration.days * 24 * 60 * 60 * 10 ** 6))

    test_duration = property(_get_test_duration, _set_test_duration)

    class Meta:
        ordering = ['-import_assigned_date']

    def show_device(self):
        all_attributes = self.attributes.all()
        for one_attributes in all_attributes:
            if one_attributes.name == "target":
                return one_attributes.value

        for one_attributes in all_attributes:
            if one_attributes.name == "target.hostname":
                return one_attributes.value

        for one_attributes in all_attributes:
            if one_attributes.name == "target.device_type":
                return one_attributes.value
        return "Target Device"

    def get_test_params(self):
        """When test_params are available return it as a dict after converting
        the dict to contain normal strings without unicode notation. If there
        are no test parameters, then we return None.
        """
        for src in self.sources.all():
            if src.test_params:
                test_struct = ast.literal_eval(src.test_params)
                if type(test_struct) == dict:
                    test_params = {}
                    for k, v in test_struct.items():
                        test_params[str(k)] = str(v)
                    return test_params
        return None


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
        verbose_name=_(u"Content"),
        help_text=_(u"Attachment content"),
        upload_to='attachments',
        null=True)

    content_filename = models.CharField(
        verbose_name=_(u"Content file name"),
        help_text=_(u"Name of the original attachment"),
        max_length=256)

    mime_type = models.CharField(
        verbose_name=_(u"MIME type"),
        max_length=64)

    public_url = models.URLField(
        verbose_name=_(u"Public URL"),
        max_length=512,
        blank=True)

    # Content type plumbing
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = generic.GenericForeignKey('content_type', 'object_id')

    def __unicode__(self):
        return self.content_filename

    def is_test_run_attachment(self):
        if (self.content_type.app_label == 'dashboard_app' and
                self.content_type.model == 'testrun'):
            return True

    def is_test_result_attachment(self):
        if (self.content_type.app_label == 'dashboard_app' and
                self.content_type.model == 'testresult'):
            return True

    @property
    def test_run(self):
        if self.is_test_run_attachment():
            return self.content_object

    @property
    def test_result(self):
        if self.is_test_result_attachment():
            return self.content_object

    @property
    def bundle(self):
        if self.is_test_result_attachment():
            run = self.test_result.test_run
            return run.bundle
        elif self.is_test_run_attachment():
            run = self.test_run
            return run.bundle
        return None

    def get_content_size(self):
        try:
            return filesizeformat(self.content.size)
        except OSError:
            return "unknown size"

    @models.permalink
    def get_download_url(self):
        return ("dashboard_app.views.attachment_download",
                [self.pk])

    @models.permalink
    def get_view_url(self):
        return ("dashboard_app.views.attachment_view",
                [self.pk])

    def is_viewable(self):
        return self.mime_type in ['text/plain']

    def is_archived(self):
        """Checks if the attachment file was archived.
        """
        last_info = os.path.join(settings.ARCHIVE_ROOT, 'attachments',
                                 'last.info')

        if os.path.exists(last_info):
            with open(last_info, 'r') as last:
                last_archived = int(last.read())
                last.close()

            if self.id <= last_archived:
                return True
            else:
                return False

        return False


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
        related_name="test_results"
    )

    test_case = models.ForeignKey(
        TestCase,
        related_name="test_results",
        null=True,
        blank=True
    )

    @property
    def test(self):
        return self.test_run.test

    # Core attributes

    result = models.PositiveSmallIntegerField(
        verbose_name=_(u"Result"),
        help_text=_(u"Result classification to pass/fail group"),
        choices=(
            (RESULT_PASS, _(u"Test passed")),
            (RESULT_FAIL, _(u"Test failed")),
            (RESULT_SKIP, _(u"Test skipped")),
            (RESULT_UNKNOWN, _(u"Unknown outcome")))
    )

    measurement = models.CharField(
        blank=True,
        max_length=512,
        help_text=_(u"Arbitrary value that was measured as a part of this test."),
        null=True,
        verbose_name=_(u"Measurement"),
    )

    # Misc attributes

    filename = models.CharField(
        blank=True,
        max_length=1024,
        null=True,
    )

    lineno = models.PositiveIntegerField(
        blank=True,
        null=True
    )

    message = models.TextField(
        blank=True,
        max_length=1024,
        null=True
    )

    microseconds = models.BigIntegerField(
        blank=True,
        null=True
    )

    timestamp = models.DateTimeField(
        blank=True,
        null=True
    )

    relative_index = models.PositiveIntegerField(
        help_text=_(u"The relative order of test results in one test run")
    )

    comments = models.TextField(
        blank=True,
        null=True
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

    # Attachments

    attachments = generic.GenericRelation(Attachment)

    # Duration property

    def _get_duration(self):
        if self.microseconds is None:
            return None
        else:
            return datetime.timedelta(microseconds=self.microseconds)

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


class Image(models.Model):

    name = models.SlugField(max_length=1024, unique=True)

    filter = models.ForeignKey("TestRunFilter", related_name='+', null=True)

    def __unicode__(self):
        owner_name = getattr(self.filter, 'owner_name', '<NULL>')
        return '%s, based on %s' % (self.name, owner_name)

    @models.permalink
    def get_absolute_url(self):
        return ("dashboard_app.views.images.image_report_detail", (), dict(name=self.name))


class ImageSet(models.Model):

    name = models.CharField(max_length=1024, unique=True)

    images = models.ManyToManyField(Image)

    def __unicode__(self):
        return self.name


class BugLink(models.Model):

    bug_link = models.CharField(
        verbose_name=_(u"Bug Link"),
        max_length=1024,
        blank=True,
        help_text=_help_max_length(1024))

    test_runs = models.ManyToManyField(
        TestRun,
        blank=True,
        related_name='bug_links'
    )

    test_result = models.ManyToManyField(
        TestResult,
        blank=True,
        related_name='bug_links'
    )

    def __unicode__(self):
        return unicode(self.bug_link)


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
        help_text=_(u"The index of this test in the filter"))

    def __unicode__(self):
        return unicode(self.test)


class TestRunFilterTestCase(models.Model):

    test_case = models.ForeignKey(TestCase, related_name="+")
    test = models.ForeignKey(TestRunFilterTest, related_name="cases")
    index = models.PositiveIntegerField(
        help_text=_(u"The index of this case in the test"))

    def __unicode__(self):
        return unicode(self.test_case)


class TestRunFilter(models.Model):

    owner = models.ForeignKey(User)

    name = models.SlugField(
        max_length=1024,
        help_text=("The <b>name</b> of a filter is used to refer to it in "
                   "the web UI and in email notifications triggered by this "
                   "filter."))

    @property
    def owner_name(self):
        return '~%s/%s' % (self.owner.username, self.name)

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

    def as_data(self):
        tests = []
        for trftest in self.tests.order_by('index').prefetch_related('cases'):
            tests.append({
                'test': trftest.test,
                'test_cases': [trftestcase.test_case for trftestcase in trftest.cases.all().select_related('test_case')],
            })
        return {
            'bundle_streams': self.bundle_streams.all(),
            'attributes': self.attributes.all().values_list('name', 'value'),
            'tests': tests,
            'build_number_attribute': self.build_number_attribute,
            'uploaded_by': self.uploaded_by,
        }

    def __unicode__(self):
        return "<TestRunFilter ~%s/%s>" % (self.owner.username, self.name)

    # given bundle:
    # select from filter
    #  where bundle.bundle_stream in filter.bundle_streams
    #    and filter.test in (select test from bundle.test_runs)
    #    and all the attributes on the filter are on a testrun in the bundle
    #       = the minimum over testrun (the number of attributes on the filter that are not on the testrun) is 0
    #    and (filter.test_case is null
    #         or filter.test_case in select test_case from bundle.test_runs.test_results.test_cases)

    @classmethod
    def matches_against_bundle(cls, bundle):
        from dashboard_app.filters import FilterMatch
        bundle_filters = bundle.bundle_stream.testrunfilter_set.all()
        attribute_filters = bundle_filters.extra(
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
        )
        no_test_filters = list(attribute_filters.annotate(models.Count('tests')).filter(tests__count=0))
        attribute_filters = list(attribute_filters)
        no_test_case_filters = list(
            TestRunFilter.objects.filter(
                id__in=TestRunFilterTest.objects.filter(
                    filter__in=attribute_filters, test__in=bundle.test_runs.all()
                    .values('test_id')).annotate(models.Count('cases')).filter(cases__count=0).values('filter__id'),
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
            fail_count=models.Sum('test_runs__denormalization__count_fail')
        ).get(id=bundle.id)
        for filter in filters:
            match = FilterMatch()
            match.filter = filter
            match.filter_data = filter.as_data()
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

    @models.permalink
    def get_absolute_url(self):
        return (
            "dashboard_app.views.filters.views.filter_detail",
            [self.owner.username, self.name])

    def is_accessible_by(self, user):
        # If any of bundle streams is not accessible by this user, restrict
        # access to this filter as well.
        for bundle_stream in self.bundle_streams.all():
            if not bundle_stream.is_accessible_by(user):
                return False

        return True


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
                        if not t['test_cases']:
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


def send_image_report_notifications(sender, bundle):
    try:
        matches = []
        charts = ImageReportChart.objects.filter(
            imagechartuser__has_subscription=True)
        url_prefix = 'http://%s' % get_domain()

        filter_matches = TestRunFilter.matches_against_bundle(bundle)

        for chart in charts:
            if chart.target_goal:

                chart_filters = [chart_filter.filter for chart_filter in
                                 chart.imagechartfilter_set.all()]
                chart_tests = []
                for chart_filter in chart.imagechartfilter_set.all():
                    chart_tests += chart_filter.chart_tests

                chart_tests = [chart_test.test for chart_test in chart_tests]

                for filter_match in filter_matches:

                    if filter_match.filter in chart_filters:
                        if chart.chart_type == "pass/fail":
                            for test_run in filter_match.test_runs:
                                if test_run.test in chart_tests:

                                    denorm = test_run.denormalization
                                    if denorm.count_pass < chart.target_goal:
                                        matches.append(test_run)

                        elif chart.chart_type == "measurement":
                            for test_result in filter_match.specific_results:
                                if test_result.test_case in chart_tests:
                                    if test_result.measurement <\
                                            chart.target_goal:
                                        matches.append(test_result)

                        elif chart.chart_type == "attributes":
                            for test_run in filter_match.test_runs:
                                if test_run.test in chart_tests:
                                    for attr in chart_test.attributes:
                                        try:
                                            value = float(
                                                test_run.attributes.get(
                                                    name=attr).value)
                                        except ValueError:
                                            # Do not user attributes which are
                                            # not numbers.
                                            continue
                                        if value < chart.target_goal:
                                            if test_run not in matches:
                                                matches.append(test_run)

                for chart_user in chart.imagechartuser_set.all():
                    if matches:
                        title = "LAVA image report test failure notification: %s" % chart.name
                        template = "dashboard_app/chart_subscription_mail.txt"
                        data = {'bundle': bundle, 'user': chart_user.user,
                                'image_report': chart.image_report,
                                'matches': matches, 'url_prefix': url_prefix}
                        logging.info("sending notification to %s",
                                     chart_user.user)
                        send_notification(title, template, data,
                                          chart_user.user.email)

    except:
        logging.exception("send_image_report_notifications failed")
        raise


def send_notification(title, template, data, address):

    mail = render_to_string(template, data)
    send_mail(title, mail, settings.SERVER_EMAIL, [address])


def send_bundle_notifications(sender, bundle, **kwargs):
    try:
        from dashboard_app.filters import evaluate_filter

        recipients = TestRunFilterSubscription.recipients_for_bundle(bundle)
        url_prefix = 'http://%s' % get_domain()
        for user, matches in recipients.items():
            logging.info("sending bundle notifications to %s", user)
            for match in matches:
                test_names = set()
                for test_run in match.test_runs:
                    test_names.add(test_run.test.test_id)

                # Get the last two bundles.
                filter_matches = list(evaluate_filter(user, match.filter.as_data())[:2])
                # We're interested in the previous bundle.
                previous_match = filter_matches[1]

                test_names_previous = set()
                for test_run in previous_match.test_runs:
                    test_names_previous.add(test_run.test.test_id)

                # Get differences between the tests in this and
                # previous bundle.
                test_diff_left = list(set(test_names) -
                                      set(test_names_previous))
                test_diff_right = list(set(test_names_previous) -
                                       set(test_names))

                # Total test count and pass test count diff.
                test_count_diff = False
                if match.pass_count != previous_match.pass_count or \
                   match.result_count != previous_match.result_count:
                    test_count_diff = True

                data = {
                    'bundle': bundle, 'user': user, 'url_prefix': url_prefix,
                    'match': match, 'previous_match': previous_match,
                    'test_diff_left': test_diff_left,
                    'test_diff_right': test_diff_right,
                    'test_count_diff': test_count_diff,
                }
                template = 'dashboard_app/filter_subscription_mail.txt'
                title = "LAVA result notification: %s" % match.filter.name
                send_notification(title, template, data, user.email)

    except:
        logging.exception("send_bundle_notifications failed")
        raise


def get_domain():
    domain = '???'
    try:
        site = Site.objects.get_current()
    except (Site.DoesNotExist, ImproperlyConfigured):
        pass
    else:
        domain = site.domain

    return domain


def bundle_deserialization_callback(sender, bundle, **kwargs):
    send_bundle_notifications(sender, bundle, **kwargs)
    send_image_report_notifications(sender, bundle)
    update_image_charts(bundle)


def update_image_charts(bundle):

    filter_matches = TestRunFilter.matches_against_bundle(bundle)

    for filter in filter_matches:
        chart_filters = ImageChartFilter.objects.filter(
            image_chart_filter=filter)
        for chart_filter in chart_filters:
            chart_filter.save()


bundle_was_deserialized.connect(bundle_deserialization_callback)


class PMQABundleStream(models.Model):

    bundle_stream = models.ForeignKey(BundleStream, related_name='+')


class ImageReportGroup(models.Model):

    name = models.SlugField(max_length=1024, unique=True)

    def __unicode__(self):
        return self.name


class ImageReport(models.Model):

    name = models.SlugField(max_length=1024, unique=True)

    image_report_group = models.ForeignKey(
        ImageReportGroup,
        default=None,
        null=True,
        on_delete=models.CASCADE)

    user = models.ForeignKey(
        User,
        default=None,
        on_delete=models.CASCADE)

    description = models.TextField(blank=True, null=True)

    is_published = models.BooleanField(
        default=False,
        verbose_name='Published')

    def __unicode__(self):
        return self.name

    @models.permalink
    def get_absolute_url(self):
        return ("dashboard_app.views.image_reports.views.image_report_display",
                (), dict(name=self.name))

    def is_accessible_by(self, user):
        # If any of bundle streams is not accessible by this user, restrict
        # access to this image report as well.
        for chart in self.imagereportchart_set.all():
            for chart_filter in chart.imagechartfilter_set.all():
                for bundle_stream in chart_filter.filter.bundle_streams.all():
                    if not bundle_stream.is_accessible_by(user):
                        return False

        return True


# Chart types
CHART_TYPES = ((r'pass/fail', 'Pass/Fail'),
               (r'measurement', 'Measurement'),
               (r'attributes', 'Attributes'))
# Chart representation
REPRESENTATION_TYPES = ((r'lines', 'Lines'),
                        (r'bars', 'Bars'))
# Chart visibility
CHART_VISIBILITY = ((r'chart', 'Chart only'),
                    (r'table', 'Result table only'),
                    (r'both', 'Both'))


class ImageReportChart(models.Model):

    class Meta:
        unique_together = ("image_report", "name")
        ordering = ['relative_index']

    name = models.CharField(max_length=100)

    description = models.TextField(blank=True, null=True)

    image_report = models.ForeignKey(
        ImageReport,
        default=None,
        null=False,
        on_delete=models.CASCADE)

    chart_type = models.CharField(
        max_length=20,
        choices=CHART_TYPES,
        verbose_name='Chart type',
        blank=False,
        default="pass/fail",
    )

    target_goal = models.DecimalField(
        blank=True,
        decimal_places=5,
        max_digits=10,
        null=True,
        verbose_name='Target goal')

    chart_height = models.PositiveIntegerField(
        default=300,
        validators=[
            MinValueValidator(200),
            MaxValueValidator(400)
        ],
        verbose_name='Chart height')

    is_interactive = models.BooleanField(
        default=False,
        verbose_name='Interactive')

    is_data_table_visible = models.BooleanField(
        default=False,
        verbose_name='Data table visible')

    is_percentage = models.BooleanField(
        default=False,
        verbose_name='Percentage')

    is_aggregate_results = models.BooleanField(
        default=True,
        verbose_name='Aggregate parametrized results')

    chart_visibility = models.CharField(
        max_length=20,
        choices=CHART_VISIBILITY,
        verbose_name='Chart visibility',
        blank=False,
        default="chart",
    )

    is_build_number = models.BooleanField(
        default=True,
        verbose_name='Use build number')

    xaxis_attribute = models.CharField(
        blank=True,
        null=True,
        max_length=20,
        verbose_name='X-axis attribute')

    relative_index = models.PositiveIntegerField(
        default=0,
        verbose_name='Order in the report')

    def __unicode__(self):
        return self.name

    @models.permalink
    def get_absolute_url(self):
        return ("dashboard_app.views.image_reports.views.image_chart_detail",
                (), dict(name=self.image_report.name, id=self.id))

    def get_chart_data(self, user):
        """
        Pack data from filter to json format based on
        selected tests/test cases.
        """

        chart_data = self.get_basic_chart_data()
        if user.is_authenticated():
            chart_data["user"] = self.get_user_chart_data(user)

        chart_data["filters"] = {}
        for image_chart_filter in self.imagechartfilter_set.all():

            chart_data["filters"][image_chart_filter.filter.id] = image_chart_filter.get_basic_filter_data()

            filter_data = image_chart_filter.filter.as_data()

            if self.chart_type == "pass/fail":

                self.get_chart_test_data(user, image_chart_filter, filter_data,
                                         chart_data)

            elif self.chart_type == "measurement":
                self.get_chart_test_case_data(user, image_chart_filter,
                                              filter_data, chart_data)

            elif self.chart_type == "attributes":
                self.get_chart_attributes_data(user, image_chart_filter,
                                               filter_data, chart_data)

        return chart_data

    def get_basic_chart_data(self):
        chart_data = {}
        fields = ["id", "name", "chart_type", "description", "target_goal",
                  "chart_height", "is_percentage", "chart_visibility",
                  "xaxis_attribute"]

        for field in fields:
            chart_data[field] = getattr(self, field)

        chart_data["report_name"] = self.image_report.name

        chart_data["test_data"] = []
        return chart_data

    def get_user_chart_data(self, user):

        chart_data = {}
        try:
            chart_user = ImageChartUser.objects.get(image_chart=self, user=user)
            chart_data["start_date"] = chart_user.start_date
            chart_data["is_legend_visible"] = chart_user.is_legend_visible
            chart_data["is_delta"] = chart_user.is_delta
            chart_data["has_subscription"] = chart_user.has_subscription

        except ImageChartUser.DoesNotExist:
            # Leave an empty dict.
            pass

        chart_data["hidden_tests"] = []
        if self.chart_type == "pass/fail":

            chart_test_users = ImageChartTestUser.objects.filter(
                image_chart_test__image_chart_filter__image_chart=self)

            for chart_test_user in chart_test_users:
                if not chart_test_user.is_visible:
                    chart_data["hidden_tests"].append(
                        chart_test_user.image_chart_test.id)
        elif self.chart_type == "measurement":
            chart_test_case_users = ImageChartTestCaseUser.objects.filter(
                image_chart_test_case__image_chart_filter__image_chart=self)
            for chart_test_case_user in chart_test_case_users:
                if not chart_test_case_user.is_visible:
                    chart_data["hidden_tests"].append(
                        chart_test_case_user.image_chart_test_case.id)
        elif self.chart_type == "attributes":
            chart_users = ImageChartTestAttributeUser.objects.filter(
                image_chart_test_attribute__image_chart_test__image_chart_filter__image_chart=self)

            for chart_user in chart_users:
                if not chart_user.is_visible:
                    test_id = chart_user.image_chart_test_attribute.\
                        image_chart_test.id
                    chart_data["hidden_tests"].append(
                        "%s-%s" % (test_id,
                                   chart_user.image_chart_test_attribute.name))

        return chart_data

    def get_chart_test_data(self, user, image_chart_filter, filter_data,
                            chart_data):
        from dashboard_app.filters import evaluate_filter

        # Prepare to filter the tests and test cases for the
        # evaluate_filter call.
        tests = []

        selected_chart_tests = image_chart_filter.imagecharttest_set.all().prefetch_related('imagecharttestattribute_set')

        # Leave chart_data empty if there are no tests available.
        if not selected_chart_tests:
            return

        for chart_test in selected_chart_tests:
            tests.append({
                'test': chart_test.test,
                'test_cases': [],
            })

        filter_data['tests'] = tests

        matches = list(evaluate_filter(user, filter_data,
                                       prefetch_related=['bug_links'])[:50])
        matches.reverse()

        # Store metadata changes.
        metadata = {}

        for match in matches:
            for test_run in match.test_runs:

                denorm = test_run.denormalization

                bug_links = sorted(
                    [b.bug_link for b in test_run.bug_links.all()])

                metadata_content = {}

                test_id = test_run.test.test_id

                # Find corresponding chart_test object.
                chart_test = None
                for ch_test in selected_chart_tests:
                    if ch_test.test == test_run.test:
                        chart_test = ch_test
                        break

                if test_id not in metadata.keys():
                    metadata[test_id] = {}

                alias = None
                chart_test_id = None
                if chart_test:
                    chart_test_id = chart_test.id
                    # Metadata delta content. Contains attribute names as keys
                    # and value is tuple with old and new value.
                    # If specific attribute's value didn't change since the
                    # last test run, do not include that attr.
                    for attr in chart_test.attributes:
                        if attr not in metadata[test_id].keys():
                            try:
                                metadata[test_id][attr] = \
                                    test_run.attributes.get(name=attr).value
                            except NamedAttribute.DoesNotExist:
                                # Skip this attribute.
                                pass
                        else:
                            old_value = metadata[test_id][attr]
                            new_value = test_run.attributes.get(
                                name=attr).value
                            if old_value != new_value:
                                metadata_content[attr] = (old_value, new_value)
                            metadata[test_id][attr] = new_value

                    alias = chart_test.name

                if not alias:
                    alias = "%s: %s" % (image_chart_filter.filter.name,
                                        test_id)

                # Add comments flag to indicate whether comments do exist in
                # any of the test result in this test run.
                has_comments = test_run.test_results.exclude(
                    comments__isnull=True).count() != 0

                test_filter_id = "%s-%s" % (test_id, image_chart_filter.id)

                # Calculate percentages.
                percentage = 0
                if self.is_percentage:
                    if denorm.count_all() != 0:
                        percentage = round(100 * float(denorm.count_pass) /
                                           denorm.count_all(), 2)

                # Find already existing chart item (this happens if we're
                # dealing with parametrized tests) and add the values instead
                # of creating new chart item.
                found = False
                if image_chart_filter.image_chart.is_aggregate_results:
                    for chart_item in chart_data["test_data"]:
                        if chart_item["test_filter_id"] == test_filter_id and \
                           chart_item["number"] == str(match.tag):
                            chart_item["passes"] += denorm.count_pass
                            chart_item["skip"] += denorm.count_skip
                            chart_item["total"] += denorm.count_all()
                            chart_item["link"] = image_chart_filter.filter.\
                                get_absolute_url()
                            chart_item["pass"] &= denorm.count_fail == 0
                            found = True

                # Use dates or build numbers.
                build_number = str(test_run.bundle.uploaded_on)
                if self.is_build_number:
                    build_number = str(match.tag)

                # Set attribute based on xaxis_attribute.
                attribute = None
                if self.xaxis_attribute:
                    try:
                        attribute = test_run.attributes.get(
                            name=self.xaxis_attribute).value
                    except:
                        pass

                # If no existing chart item was found, create a new one.
                if not image_chart_filter.image_chart.is_aggregate_results or \
                   not found:
                    chart_item = {
                        "filter_rep": image_chart_filter.representation,
                        "test_filter_id": test_filter_id,
                        "chart_test_id": chart_test_id,
                        "link": test_run.get_absolute_url(),
                        "bundle_link": test_run.bundle.get_absolute_url(),
                        "alias": alias,
                        "number": build_number,
                        "date": str(test_run.bundle.uploaded_on),
                        "attribute": attribute,
                        "pass": denorm.count_fail == 0,
                        "passes": denorm.count_pass,
                        "percentage": percentage,
                        "skip": denorm.count_skip,
                        "total": denorm.count_all(),
                        "test_run_uuid": test_run.analyzer_assigned_uuid,
                        "bug_links": bug_links,
                        "metadata_content": metadata_content,
                        "comments": has_comments,
                    }

                    chart_data["test_data"].append(chart_item)

    def get_chart_test_case_data(self, user, image_chart_filter, filter_data,
                                 chart_data):
        from dashboard_app.filters import evaluate_filter

        # Prepare to filter the tests and test cases for the
        # evaluate_filter call.
        tests = []
        test_cases = TestCase.objects.filter(imagecharttestcase__image_chart_filter__image_chart=self).distinct('id')
        tests_all = Test.objects.filter(test_cases__in=test_cases).distinct('id').prefetch_related('test_cases')

        selected_chart_test_cases = image_chart_filter.imagecharttestcase_set.all().prefetch_related('imagecharttestcaseattribute_set')

        # Leave chart_data empty if there are no test cases available.
        if not test_cases:
            return

        for test in tests_all:
            tests.append({
                'test': test,
                'test_cases': [test_case for test_case in test_cases if test_case in test.test_cases.all()],
            })

        filter_data['tests'] = tests
        matches = list(evaluate_filter(user, filter_data,
                                       prefetch_related=['bug_links'])[:50])
        matches.reverse()

        # Store metadata changes.
        metadata = {}

        for match in matches:
            for test_result in match.specific_results:

                bug_links = sorted(
                    [b.bug_link for b in test_result.bug_links.all()])

                metadata_content = {}

                test_case_id = test_result.test_case.test_case_id
                if test_case_id not in metadata.keys():
                    metadata[test_case_id] = {}

                # Find corresponding chart_test_case object.
                chart_test_case = None
                for ch_test_case in selected_chart_test_cases:
                    if ch_test_case.test_case == test_result.test_case:
                        chart_test_case = ch_test_case
                        break

                alias = None
                chart_test_id = None
                if chart_test_case:
                    chart_test_id = chart_test_case.id
                    # Metadata delta content. Contains attribute names as
                    # keys and value is tuple with old and new value.
                    # If specific attribute's value didn't change since the
                    # last test result, do not include that attr.
                    for attr in chart_test_case.attributes:
                        if attr not in metadata[test_case_id].keys():
                            try:
                                metadata[test_case_id][attr] = \
                                    test_result.test_run.attributes.get(
                                        name=attr).value
                            except NamedAttribute.DoesNotExist:
                                # Skip this attribute.
                                pass
                        else:
                            old_value = metadata[test_case_id][attr]
                            new_value = test_result.test_run.attributes.get(
                                name=attr).value
                            if old_value != new_value:
                                metadata_content[attr] = (old_value, new_value)
                                metadata[test_case_id][attr] = new_value

                    alias = chart_test_case.name

                if not alias:
                    alias = "%s: %s: %s" % (
                        image_chart_filter.filter.name,
                        test_result.test.test_id,
                        test_case_id
                    )

                test_filter_id = "%s-%s" % (test_case_id.replace(" ", ""),
                                            image_chart_filter.id)

                # Use dates or build numbers.
                build_number = str(test_result.test_run.bundle.uploaded_on)
                if self.is_build_number:
                    build_number = str(match.tag)

                # Set attribute based on xaxis_attribute.
                attribute = None
                if self.xaxis_attribute:
                    attribute = test_run.attributes.get(
                        name=self.xaxis_attribute).value

                chart_item = {
                    "filter_rep": image_chart_filter.representation,
                    "alias": alias,
                    "test_filter_id": test_filter_id,
                    "chart_test_id": chart_test_id,
                    "units": test_result.units,
                    "measurement": test_result.measurement,
                    "link": test_result.get_absolute_url(),
                    "pass": test_result.result == 0,
                    "number": build_number,
                    "date": str(test_result.test_run.bundle.uploaded_on),
                    "attribute": attribute,
                    "test_run_uuid": test_result.test_run.analyzer_assigned_uuid,
                    "bug_links": bug_links,
                    "metadata_content": metadata_content,
                    "comments": test_result.comments,
                }
                chart_data["test_data"].append(chart_item)

    def get_chart_attributes_data(self, user, image_chart_filter, filter_data,
                                  chart_data):
        from dashboard_app.filters import evaluate_filter

        # Prepare to filter the tests and test cases for the
        # evaluate_filter call.
        tests = []

        selected_chart_tests = image_chart_filter.imagecharttest_set.all().prefetch_related('imagecharttestattribute_set')

        # Leave chart_data empty if there are no tests available.
        if not selected_chart_tests:
            return

        for chart_test in selected_chart_tests:
            tests.append({
                'test': chart_test.test,
                'test_cases': [],
            })

        filter_data['tests'] = tests

        matches = list(evaluate_filter(user, filter_data,
                                       prefetch_related=['bug_links'])[:50])
        matches.reverse()

        for match in matches:
            for test_run in match.test_runs:

                denorm = test_run.denormalization

                bug_links = sorted(
                    [b.bug_link for b in test_run.bug_links.all()])

                test_id = test_run.test.test_id

                # Find corresponding chart_test object.
                chart_test = None
                for ch_test in selected_chart_tests:
                    if ch_test.test == test_run.test:
                        chart_test = ch_test
                        break

                alias = None
                chart_test_id = None
                if chart_test:
                    chart_test_id = chart_test.id
                    for attr in chart_test.attributes:
                        try:
                            value = float(
                                test_run.attributes.get(name=attr).value)
                        except (NamedAttribute.DoesNotExist, ValueError):
                            # Skip this attribute.
                            continue

                        if chart_test.name:
                            test_name = chart_test.name
                        else:
                            test_name = test_id

                        alias = "%s: %s" % (test_name,
                                            attr.replace(" ", ""))

                        test_filter_id = "%s-%s-%s" % (test_id,
                                                       image_chart_filter.id,
                                                       attr.replace(" ", ""))

                        # Use dates or build numbers.
                        build_number = str(test_run.bundle.uploaded_on)
                        if self.is_build_number:
                            build_number = str(match.tag)

                        chart_item = {
                            "filter_rep": image_chart_filter.representation,
                            "test_filter_id": test_filter_id,
                            "chart_test_id": "%s-%s" % (chart_test_id, attr),
                            "link": test_run.get_absolute_url(),
                            "alias": alias,
                            "number": build_number,
                            "date": str(test_run.bundle.uploaded_on),
                            "pass": denorm.count_fail == 0,
                            "attr_value": value,
                            "test_run_uuid": test_run.analyzer_assigned_uuid,
                            "bug_links": bug_links,
                        }

                        chart_data["test_data"].append(chart_item)

    def get_supported_attributes(self, user):

        # Get all attributes which appear in all the tests included
        # in all filters in this particular chart.
        custom_attrs = None
        for chart_filter in self.imagechartfilter_set.all():
            for chart_test in chart_filter.imagecharttest_set.all():
                if not custom_attrs:
                    custom_attrs = chart_test.get_available_attributes(user)
                else:
                    custom_attrs = list(
                        set(chart_test.get_available_attributes(user)) &
                        set(custom_attrs)
                    )

        return custom_attrs


class ImageChartFilter(models.Model):

    image_chart = models.ForeignKey(
        ImageReportChart,
        null=False,
        on_delete=models.CASCADE)

    filter = models.ForeignKey(
        TestRunFilter,
        null=True,
        on_delete=models.SET_NULL)

    representation = models.CharField(
        max_length=20,
        choices=REPRESENTATION_TYPES,
        verbose_name='Representation',
        blank=False,
        default="lines",
    )

    is_all_tests_included = models.BooleanField(
        default=False,
        verbose_name='Include all tests from this filter'
    )

    @property
    def chart_tests(self):
        if self.image_chart.chart_type == "measurement":
            return self.imagecharttestcase_set.all()
        else:
            return self.imagecharttest_set.all()

    def get_basic_filter_data(self):
        return {
            "owner": self.filter.owner.username,
            "link": self.filter.get_absolute_url(),
            "name": self.filter.name,
        }

    def id_slug(self):
        return slugify(self.id)

    @models.permalink
    def get_absolute_url(self):
        return (
            "dashboard_app.views.image_reports.views.image_chart_filter_detail",
            (), dict(name=self.image_chart.image_report.name,
                     id=self.image_chart.id, slug=self.id))

    def save(self, *args, **kwargs):
        """
        Save this instance.

        Add all tests to the image report filter if is_all_tests_included
        flag is set.
        """
        result = super(ImageChartFilter, self).save(*args, **kwargs)
        if self.image_chart.chart_type == "pass/fail":
            tests = [chart_test.test.test_id for chart_test in self.chart_tests]
            all_filter_tests = Test.objects.filter(
                test_runs__bundle__bundle_stream__testrunfilter__id=self.filter.id).distinct('test_id')
            for test in all_filter_tests:
                if test.test_id not in tests:
                    chart_test = ImageChartTest(image_chart_filter=self,
                                                test=test)
                    chart_test.save()

        return result


class ImageChartTest(models.Model):

    class Meta:
        unique_together = ("image_chart_filter", "test")

    image_chart_filter = models.ForeignKey(
        ImageChartFilter,
        null=False,
        on_delete=models.CASCADE)

    test = models.ForeignKey(
        Test,
        null=False,
        on_delete=models.CASCADE)

    name = models.CharField(max_length=200)

    @property
    def test_name(self):
        return self.test.test_id

    def get_attributes(self):
        return [str(attr.name) for attr in
                self.imagecharttestattribute_set.all()]

    def set_attributes(self, input):
        ImageChartTestAttribute.objects.filter(image_chart_test=self).delete()
        for value in input:
            attr = ImageChartTestAttribute(image_chart_test=self, name=value)
            attr.save()

    attributes = property(get_attributes, set_attributes)

    def get_available_attributes(self, user):

        from dashboard_app.filters import evaluate_filter

        content_type_id = ContentType.objects.get_for_model(TestRun).id
        tests = [{
            'test': self.test,
            'test_cases': [],
        }]

        filter_data = self.image_chart_filter.filter.as_data()
        filter_data['tests'] = tests
        matches = list(evaluate_filter(user, filter_data)[:1])
        if not matches or not matches[0].test_runs:
            return list()
        test_run_id = matches[0].test_runs[0].id

        result = NamedAttribute.objects.all()
        result = result.filter(
            content_type_id=content_type_id,
            object_id=test_run_id).distinct().order_by('name').values_list('name', flat=True)

        attributes = [str(name) for name in result]
        return list(set(attributes))


class ImageChartTestAttribute(models.Model):

    image_chart_test = models.ForeignKey(
        ImageChartTest,
        null=False,
        on_delete=models.CASCADE)

    name = models.TextField(blank=False, null=False)


class ImageChartTestCase(models.Model):

    class Meta:
        unique_together = ("image_chart_filter", "test_case")

    image_chart_filter = models.ForeignKey(
        ImageChartFilter,
        null=False,
        on_delete=models.CASCADE)

    test_case = models.ForeignKey(
        TestCase,
        null=False,
        on_delete=models.CASCADE)

    name = models.CharField(max_length=200)

    @property
    def test_name(self):
        return self.test_case.test_case_id

    def get_attributes(self):
        return [str(attr.name) for attr in
                self.imagecharttestcaseattribute_set.all()]

    def set_attributes(self, input):
        ImageChartTestCaseAttribute.objects.filter(
            image_chart_test_case=self).delete()
        for value in input:
            attr = ImageChartTestCaseAttribute(
                image_chart_test_case=self, name=value)
            attr.save()

    attributes = property(get_attributes, set_attributes)

    def get_available_attributes(self, user):

        from dashboard_app.filters import evaluate_filter

        content_type_id = ContentType.objects.get_for_model(TestRun).id
        tests = [{
            'test': self.test_case.test,
            'test_cases': [],
        }]

        filter_data = self.image_chart_filter.filter.as_data()
        filter_data['tests'] = tests
        matches = list(evaluate_filter(user, filter_data)[:1])

        # If no matches are found, return empty list.
        if len(matches) == 0:
            return list()

        test_run_id = matches[0].test_runs[0].id

        result = NamedAttribute.objects.all()
        result = result.filter(
            content_type_id=content_type_id,
            object_id=test_run_id).distinct().order_by('name').values_list('name', flat=True)

        attributes = [str(name) for name in result]
        return list(set(attributes))


class ImageChartTestCaseAttribute(models.Model):

    image_chart_test_case = models.ForeignKey(
        ImageChartTestCase,
        null=False,
        on_delete=models.CASCADE)

    name = models.TextField(blank=False, null=False)


class ImageChartUser(models.Model):

    class Meta:
        unique_together = ("image_chart", "user")

    image_chart = models.ForeignKey(
        ImageReportChart,
        null=False,
        on_delete=models.CASCADE)

    user = models.ForeignKey(
        User,
        null=False,
        on_delete=models.CASCADE)

    # Start date can actually also be start build number, ergo char, not date.
    # Also, we do not store end date(build number) since user's only want
    # to see the latest data.
    start_date = models.CharField(max_length=20)

    is_legend_visible = models.BooleanField(
        default=True,
        verbose_name='Toggle legend')

    has_subscription = models.BooleanField(
        default=False,
        verbose_name='Subscribed to target goal')

    is_delta = models.BooleanField(
        default=False,
        verbose_name='Delta reporting')


class ImageChartTestUser(models.Model):
    """
    Stores information which tests user has hidden in the image chart.
    """

    class Meta:
        unique_together = ("image_chart_test", "user")

    image_chart_test = models.ForeignKey(
        ImageChartTest,
        null=False,
        on_delete=models.CASCADE)

    user = models.ForeignKey(
        User,
        null=False,
        on_delete=models.CASCADE)

    is_visible = models.BooleanField(
        default=True,
        verbose_name='Visible')


class ImageChartTestCaseUser(models.Model):
    """
    Stores information which test cases user has hidden in the image chart.
    """

    class Meta:
        unique_together = ("image_chart_test_case", "user")

    image_chart_test_case = models.ForeignKey(
        ImageChartTestCase,
        null=False,
        on_delete=models.CASCADE)

    user = models.ForeignKey(
        User,
        null=False,
        on_delete=models.CASCADE)

    is_visible = models.BooleanField(
        default=True,
        verbose_name='Visible')


class ImageChartTestAttributeUser(models.Model):
    """
    Stores information which attributes are hidden in the image chart.
    """

    class Meta:
        unique_together = ("image_chart_test_attribute", "user")

    image_chart_test_attribute = models.ForeignKey(
        ImageChartTestAttribute,
        null=False,
        on_delete=models.CASCADE)

    user = models.ForeignKey(
        User,
        null=False,
        on_delete=models.CASCADE)

    is_visible = models.BooleanField(
        default=True,
        verbose_name='Visible')
