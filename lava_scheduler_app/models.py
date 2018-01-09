# -*- coding: utf-8 -*-
# pylint: disable=too-many-lines

from __future__ import unicode_literals

import jinja2
import logging
import os
import re
import uuid
import simplejson
import smtplib
import socket
import sys
import yaml

from django.db.models import Q
from django.conf import settings
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE
from django.contrib.postgres.fields import ArrayField
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.core.exceptions import (
    ImproperlyConfigured,
    ValidationError,
    ObjectDoesNotExist,
    MultipleObjectsReturned,
)
from django.core.mail import send_mail
from django.core.urlresolvers import reverse
from django.core.validators import validate_email
from django.db import models, IntegrityError
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.utils.safestring import mark_safe


from django_restricted_resource.models import (
    RestrictedResource,
    RestrictedResourceManager
)
from lava_scheduler_app.managers import RestrictedTestJobQuerySet
from lava_scheduler_app.schema import (
    validate_submission,
    handle_include_option,
    SubmissionException
)

from lava_scheduler_app import utils
from linaro_django_xmlrpc.models import AuthToken
from lava_scheduler_app.schema import validate_device

if sys.version_info[0] == 2:
    # Python 2.x
    from urllib2 import urlopen, Request
    from urllib import urlencode
elif sys.version_info[0] == 3:
    # For Python 3.0 and later
    from urllib.request import urlopen, Request
    from urllib.parse import urlencode

# pylint: disable=invalid-name,no-self-use,too-many-public-methods,too-few-public-methods
# pylint: disable=too-many-branches,too-many-return-statements,too-many-instance-attributes

# Make the open function accept encodings in python < 3.x
if sys.version_info[0] < 3:
    import codecs
    open = codecs.open  # pylint: disable=redefined-builtin


class JSONDataError(ValueError):
    """Error raised when JSON is syntactically valid but ill-formed."""


class DevicesUnavailableException(UserWarning):
    """Error raised when required number of devices are unavailable."""


class ExtendedUser(models.Model):

    user = models.OneToOneField(User)

    irc_handle = models.CharField(
        max_length=40,
        default=None,
        null=True,
        blank=True,
        verbose_name='IRC handle'
    )

    irc_server = models.CharField(
        max_length=40,
        default=None,
        null=True,
        blank=True,
        verbose_name='IRC server'
    )


class Tag(models.Model):

    name = models.SlugField(unique=True)

    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name.lower()


def validate_job(data):
    try:
        yaml_data = yaml.load(data)
    except yaml.YAMLError as exc:
        raise SubmissionException("Loading job submission failed: %s." % exc)

    # validate against the submission schema.
    validate_submission(yaml_data)  # raises SubmissionException if invalid.
    validate_yaml(yaml_data)  # raises SubmissionException if invalid.


def validate_yaml(yaml_data):
    if "notify" in yaml_data:
        if "recipients" in yaml_data["notify"]:
            for recipient in yaml_data["notify"]["recipients"]:
                if recipient["to"]["method"] == \
                   NotificationRecipient.EMAIL_STR:
                    if "email" not in recipient["to"] and \
                       "user" not in recipient["to"]:
                        raise SubmissionException("No valid user or email address specified.")
                else:
                    if "handle" not in recipient["to"] and \
                       "user" not in recipient["to"]:
                        raise SubmissionException("No valid user or IRC handle specified.")
                if "user" in recipient["to"]:
                    try:
                        User.objects.get(username=recipient["to"]["user"])
                    except User.DoesNotExist:
                        raise SubmissionException("%r is not an existing user in LAVA." % recipient["to"]["user"])
                elif "email" in recipient["to"]:
                    try:
                        validate_email(recipient["to"]["email"])
                    except ValidationError:
                        raise SubmissionException("%r is not a valid email address." % recipient["to"]["email"])

        if "compare" in yaml_data["notify"] and \
           "query" in yaml_data["notify"]["compare"]:
            from lava_results_app.models import Query
            query_yaml_data = yaml_data["notify"]["compare"]["query"]
            if "username" in query_yaml_data:
                try:
                    query = Query.objects.get(
                        owner__username=query_yaml_data["username"],
                        name=query_yaml_data["name"])
                    if query.content_type.model_class() != TestJob:
                        raise SubmissionException(
                            "Only TestJob queries allowed.")
                except Query.DoesNotExist:
                    raise SubmissionException(
                        "Query ~%s/%s does not exist" % (
                            query_yaml_data["username"],
                            query_yaml_data["name"]))
            else:  # Custom query.
                if query_yaml_data["entity"] != "testjob":
                    raise SubmissionException(
                        "Only TestJob queries allowed.")
                try:
                    conditions = None
                    if "conditions" in query_yaml_data:
                        conditions = query_yaml_data["conditions"]
                    Query.validate_custom_query(
                        query_yaml_data["entity"],
                        conditions
                    )
                except Exception as e:
                    raise SubmissionException(e)


class Architecture(models.Model):
    name = models.CharField(
        primary_key=True,
        verbose_name=u'Architecture version',
        help_text=u'e.g. ARMv7',
        max_length=100,
        editable=True,
    )

    def __str__(self):
        return self.pk


class ProcessorFamily(models.Model):
    name = models.CharField(
        primary_key=True,
        verbose_name=u'Processor Family',
        help_text=u'e.g. OMAP4, Exynos',
        max_length=100,
        editable=True,
    )

    def __str__(self):
        return self.pk


class Alias(models.Model):
    name = models.CharField(
        primary_key=True,
        verbose_name=u'Alias for this device-type',
        help_text=u'e.g. the device tree name(s)',
        max_length=200,
        editable=True,
    )

    def __str__(self):
        return self.pk


class BitWidth(models.Model):
    width = models.PositiveSmallIntegerField(
        primary_key=True,
        verbose_name=u'Processor bit width',
        help_text=u'integer: e.g. 32 or 64',
        editable=True,
    )

    def __str__(self):
        return "%d" % self.pk


class Core(models.Model):
    name = models.CharField(
        primary_key=True,
        verbose_name=u'CPU core',
        help_text=u'Name of a specific CPU core, e.g. Cortex-A9',
        editable=True,
        max_length=100,
    )

    def __str__(self):
        return self.pk


class DeviceType(models.Model):
    """
    A class of device, for example a pandaboard or a snowball.
    """

    name = models.SlugField(primary_key=True)

    architecture = models.ForeignKey(
        Architecture,
        related_name='device_types',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )

    processor = models.ForeignKey(
        ProcessorFamily,
        related_name='device_types',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )

    cpu_model = models.CharField(
        verbose_name=u'CPU model',
        help_text=u'e.g. a list of CPU model descriptive strings: OMAP4430 / OMAP4460',
        max_length=100,
        blank=True,
        null=True,
        editable=True,
    )

    aliases = models.ManyToManyField(
        Alias,
        related_name='device_types',
        blank=True,
    )

    bits = models.ForeignKey(
        BitWidth,
        related_name='device_types',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )

    cores = models.ManyToManyField(
        Core,
        related_name='device_types',
        blank=True,
    )

    core_count = models.PositiveSmallIntegerField(
        verbose_name=u'Total number of cores',
        help_text=u'Must be an equal number of each type(s) of core(s).',
        blank=True,
        null=True,
    )

    def __str__(self):
        return self.name

    description = models.TextField(
        verbose_name=_(u"Device Type Description"),
        max_length=200,
        null=True,
        blank=True,
        default=None
    )

    health_frequency = models.IntegerField(
        verbose_name="How often to run health checks",
        default=24
    )

    disable_health_check = models.BooleanField(
        default=False,
        verbose_name="Disable health check for devices of this type")

    HEALTH_PER_HOUR = 0
    HEALTH_PER_JOB = 1
    HEALTH_DENOMINATOR = (
        (HEALTH_PER_HOUR, 'hours'),
        (HEALTH_PER_JOB, 'jobs'),
    )

    health_denominator = models.IntegerField(
        choices=HEALTH_DENOMINATOR,
        default=HEALTH_PER_HOUR,
        verbose_name="Initiate health checks by hours or by jobs.",
        help_text=("Choose to submit a health check every N hours "
                   "or every N jobs. Balance against the duration of "
                   "a health check job and the average job duration."))

    display = models.BooleanField(default=True,
                                  help_text=("Should this be displayed in the GUI or not. This can be "
                                             "useful if you are removing all devices of this type but don't "
                                             "want to loose the test results generated by the devices."))

    owners_only = models.BooleanField(default=False,
                                      help_text="Hide this device type for all users except owners of "
                                                "devices of this type.")

    @models.permalink
    def get_absolute_url(self):
        return ("lava.scheduler.device_type.detail", [self.pk])

    def num_devices_visible_to(self, user):
        """
        Prepare a list of devices of this DeviceType which
        this user can see. If the DeviceType is not hidden,
        returns all devices of this type.
        :param user: User to check
        :return: the number of devices of this DeviceType which the
        user can see. This may be 0 if the type is hidden
        and the user owns none of the devices of this type.
        """
        devices = Device.objects.filter(device_type=self) \
                                .only('user', 'group') \
                                .select_related('user', 'group')
        if self.owners_only:
            return len([d for d in devices if d.is_owned_by(user)])
        else:
            return devices.count()

    def some_devices_visible_to(self, user):
        """
        :param user: User to check
        :return: True if some devices of this DeviceType are visible
        """
        # Grab the key from the cache if available
        version = user.id if user.id is not None else -1
        cached_value = cache.get(self.name, version=version)
        if cached_value is not None:
            return cached_value

        devices = Device.objects.filter(device_type=self) \
                                .only('state', 'health', 'user', 'group') \
                                .select_related('user', 'group')

        if self.owners_only:
            result = False
            for d in devices:
                if d.is_owned_by(user):
                    result = True
                    break
        else:
            result = devices.exists()
        # Cache the value for 30 seconds
        cache.set(self.name, result, 30, version=version)
        return result


class DefaultDeviceOwner(models.Model):
    """
    Used to override the django User model to allow one individual
    user to be specified as the default device owner.
    """
    user = models.OneToOneField(User)
    default_owner = models.BooleanField(
        verbose_name="Default owner of unrestricted devices",
        unique=True,
        default=False
    )

    def __str__(self):
        if self.user:
            return self.user.username
        return ''


class Worker(models.Model):
    """
    A worker node to which devices are attached.
    """

    hostname = models.CharField(
        verbose_name=_(u"Hostname"),
        max_length=200,
        primary_key=True,
        default=None,
        editable=True
    )

    STATE_ONLINE, STATE_OFFLINE = range(2)
    STATE_CHOICES = (
        (STATE_ONLINE, "Online"),
        (STATE_OFFLINE, "Offline"),
    )
    state = models.IntegerField(choices=STATE_CHOICES,
                                default=STATE_OFFLINE,
                                editable=False)

    HEALTH_ACTIVE, HEALTH_MAINTENANCE, HEALTH_RETIRED = range(3)
    HEALTH_CHOICES = (
        (HEALTH_ACTIVE, "Active"),
        (HEALTH_MAINTENANCE, "Maintenance"),
        (HEALTH_RETIRED, "Retired"),
    )
    health = models.IntegerField(choices=HEALTH_CHOICES,
                                 default=HEALTH_ACTIVE)

    description = models.TextField(
        verbose_name=_(u"Worker Description"),
        max_length=200,
        null=True,
        blank=True,
        default=None,
        editable=True
    )

    last_ping = models.DateTimeField(verbose_name=_(u"Last ping"),
                                     default=timezone.now)

    def __str__(self):
        return self.hostname

    def can_admin(self, user):
        return user.has_perm('lava_scheduler_app.change_worker')

    def can_update(self, user):
        if user.has_perm('lava_scheduler_app.change_worker'):
            return True
        elif user.username == "lava-health":
            return True
        else:
            return False

    @models.permalink
    def get_absolute_url(self):
        return ("lava.scheduler.worker.detail", [self.pk])

    def get_description(self):
        return mark_safe(self.description) if self.description else None

    def update_description(self, description):
        self.description = description
        self.save()

    def retired_devices_count(self):
        return self.device_set.filter(health=Device.HEALTH_RETIRED).count()

    def go_health_active(self, user):
        self.log_admin_entry(user, "%s → Active" % self.get_health_display())
        for device in self.device_set.all().select_for_update():
            device.worker_signal("go_health_active", user, self.state, self.health)
            device.save()
        self.health = Worker.HEALTH_ACTIVE

    def go_health_maintenance(self, user):
        self.log_admin_entry(user, "%s → Maintenance" % self.get_health_display())
        for device in self.device_set.all().select_for_update():
            device.worker_signal("go_health_maintenance", user, self.state, self.health)
            device.save()
        self.health = Worker.HEALTH_MAINTENANCE

    def go_health_retired(self, user):
        self.log_admin_entry(user, "%s → Retired" % self.get_health_display())
        for device in self.device_set.all().select_for_update():
            device.worker_signal("go_health_retired", user, self.state, self.health)
            device.save()
        self.health = Worker.HEALTH_RETIRED

    def go_state_offline(self):
        self.state = Worker.STATE_OFFLINE

    def go_state_online(self):
        self.state = Worker.STATE_ONLINE

    def log_admin_entry(self, user, reason, addition=False):
        if user is None:
            user = User.objects.get(username="lava-health")
        worker_ct = ContentType.objects.get_for_model(Worker)
        LogEntry.objects.log_action(
            user_id=user.id,
            content_type_id=worker_ct.pk,
            object_id=self.pk,
            object_repr=self.hostname,
            action_flag=ADDITION if addition else CHANGE,
            change_message=reason
        )


class Device(RestrictedResource):
    """
    A device that we can run tests on.
    """

    CONFIG_PATH = "/etc/lava-server/dispatcher-config/devices"
    HEALTH_CHECK_PATH = "/etc/lava-server/dispatcher-config/health-checks"

    hostname = models.CharField(
        verbose_name=_(u"Hostname"),
        max_length=200,
        primary_key=True,
    )

    device_type = models.ForeignKey(
        DeviceType, verbose_name=_(u"Device type"))

    device_version = models.CharField(
        verbose_name=_(u"Device Version"),
        max_length=200,
        null=True,
        default=None,
        blank=True,
    )

    physical_owner = models.ForeignKey(
        User, related_name='physicalowner',
        null=True,
        blank=True,
        default=None,
        verbose_name=_(u"User with physical access"),
        on_delete=models.SET_NULL,
    )

    physical_group = models.ForeignKey(
        Group, related_name='physicalgroup',
        null=True,
        blank=True,
        default=None,
        verbose_name=_(u"Group with physical access")
    )

    description = models.TextField(
        verbose_name=_(u"Device Description"),
        max_length=200,
        null=True,
        blank=True,
        default=None
    )

    tags = models.ManyToManyField(Tag, blank=True)

    # This state is a cache computed from the device health and jobs. So keep
    # it read only to the admins
    STATE_IDLE, STATE_RESERVED, STATE_RUNNING = range(3)
    STATE_CHOICES = (
        (STATE_IDLE, 'Idle'),
        (STATE_RESERVED, 'Reserved'),
        (STATE_RUNNING, 'Running'),
    )
    state = models.IntegerField(choices=STATE_CHOICES, default=STATE_IDLE,
                                editable=False)

    # The device health helps to decide what to do next with the device
    HEALTH_GOOD, HEALTH_UNKNOWN, HEALTH_LOOPING, HEALTH_BAD, HEALTH_MAINTENANCE, HEALTH_RETIRED = range(6)
    HEALTH_CHOICES = (
        (HEALTH_GOOD, 'Good'),
        (HEALTH_UNKNOWN, 'Unknown'),
        (HEALTH_LOOPING, 'Looping'),
        (HEALTH_BAD, 'Bad'),
        (HEALTH_MAINTENANCE, 'Maintenance'),
        (HEALTH_RETIRED, 'Retired')
    )
    HEALTH_REVERSE = {
        "GOOD": HEALTH_GOOD,
        "UNKNOWN": HEALTH_UNKNOWN,
        "LOOPING": HEALTH_LOOPING,
        "BAD": HEALTH_BAD,
        "MAINTENANCE": HEALTH_MAINTENANCE,
        "RETIRED": HEALTH_RETIRED,
    }
    health = models.IntegerField(choices=HEALTH_CHOICES, default=HEALTH_UNKNOWN)

    last_health_report_job = models.OneToOneField(
        "TestJob", blank=True, unique=True, null=True, related_name='+',
        on_delete=models.SET_NULL)

    # TODO: make this mandatory
    worker_host = models.ForeignKey(
        Worker,
        verbose_name=_(u"Worker Host"),
        null=True,
        blank=True,
        default=None,
        on_delete=models.SET_NULL,
    )

    is_pipeline = models.BooleanField(
        verbose_name="Pipeline device?",
        default=False,
        editable=True
    )

    def clean(self):
        """
        Complies with the RestrictedResource constraints
        by specifying the default device owner as the superuser
        upon save if none was set.
        Devices become public if no User or Group is specified
        First superuser by id is the default user if default user is None
        Devices move to that superuser if default user is None.
        """

        default_user_list = DefaultDeviceOwner.objects.all()[:1]
        if not default_user_list or len(default_user_list) == 0:
            superusers = User.objects.filter(is_superuser=True).order_by('id')[:1]
            if len(superusers) > 0:
                first_super_user = superusers[0]
                if self.group is None:
                    self.user = User.objects.filter(username=first_super_user.username)[0]
                default_owner = DefaultDeviceOwner()
                default_owner.user = User.objects.filter(username=first_super_user.username)[0]
                default_owner.save()
                first_super_user.defaultdeviceowner.user = first_super_user
                first_super_user.save()
            if self.device_type.owners_only:
                self.is_public = False
            return
        default_user = default_user_list[0]
        if self.user is None and self.group is None:
            if self.device_type.owners_only:
                self.is_public = False
            if default_user:
                self.user = User.objects.filter(id=default_user.user_id)[0]
        if self.user is not None and self.group is not None:
            raise ValidationError(
                'Cannot be owned by a user and a group at the same time')

    def __str__(self):
        r = self.hostname
        r += " (%s, health %s)" % (self.get_state_display(),
                                   self.get_health_display())
        return r

    def current_job(self):
        try:
            return self.testjobs.get(~Q(state=TestJob.STATE_FINISHED))
        except TestJob.DoesNotExist:
            return None

    @models.permalink
    def get_absolute_url(self):
        return ("lava.scheduler.device.detail", [self.pk])

    def get_simple_state_display(self):
        if self.state == Device.STATE_IDLE:
            if self.health in [Device.HEALTH_MAINTENANCE, Device.HEALTH_RETIRED]:
                return self.get_health_display()
        return self.get_state_display()

    def get_description(self):
        return mark_safe(self.description) if self.description else None

    def is_visible_to(self, user):
        """
        Checks if this device is visible to the specified user.
        Retired devices are deemed to be visible - filter these out
        explicitly where necessary.
        :param user: If empty, restricted or hidden devices always return False
        :return: True if the user can see this device
        """
        if self.device_type.owners_only:
            if not user:
                return False
            if not self.device_type.some_devices_visible_to(user):
                return False
        if not self.is_public:
            if not user:
                return False
            if not self.can_submit(user):
                return False
        return True

    def can_admin(self, user):
        if self.is_owned_by(user):
            return True
        if user.has_perm('lava_scheduler_app.change_device'):
            return True
        return False

    def can_submit(self, user):
        if self.health == Device.HEALTH_RETIRED:
            return False
        if self.is_public:
            return True
        if user.username == "lava-health":
            return True
        return self.is_owned_by(user)

    def is_valid(self, system=True):
        if not self.is_pipeline:
            return False  # V1 config cannot be checked
        rendered = self.load_configuration()
        try:
            validate_device(rendered)
        except SubmissionException:
            return False
        return True

    def log_admin_entry(self, user, reason):
        if user is None:
            user = User.objects.get(username="lava-health")
        device_ct = ContentType.objects.get_for_model(Device)
        LogEntry.objects.log_action(
            user_id=user.id,
            content_type_id=device_ct.pk,
            object_id=self.pk,
            object_repr=self.hostname,
            action_flag=CHANGE,
            change_message=reason
        )

    def testjob_signal(self, signal, job):
        if signal == "go_state_scheduling":
            self.state = Device.STATE_RESERVED

        elif signal == "go_state_scheduled":
            self.state = Device.STATE_RESERVED

        elif signal == "go_state_running":
            self.state = Device.STATE_RUNNING

        elif signal == "go_state_canceling":
            pass

        elif signal == "go_state_finished":
            self.state = Device.STATE_IDLE

            if job.health_check and self.health in [Device.HEALTH_GOOD, Device.HEALTH_UNKNOWN, Device.HEALTH_BAD]:
                self.last_health_report_job = job
                prev_health_display = self.get_health_display()
                if job.health == TestJob.HEALTH_COMPLETE:
                    self.health = Device.HEALTH_GOOD
                elif job.health == TestJob.HEALTH_INCOMPLETE:
                    self.health = Device.HEALTH_BAD
                elif job.health == TestJob.HEALTH_CANCELED:
                    self.health = Device.HEALTH_UNKNOWN
                else:
                    raise NotImplementedError("Unexpected TestJob health")
                self.log_admin_entry(None, "%s → %s" % (prev_health_display, self.get_health_display()))

        else:
            raise NotImplementedError("Unknown signal %s" % signal)

    def worker_signal(self, signal, user, prev_state, prev_health):
        # HEALTH_BAD and HEALTH_RETIRED are permanent states that are not
        # changed by worker signals
        if signal == "go_health_active":
            # When leaving retirement, don't cascade the change
            if prev_health == Worker.HEALTH_RETIRED:
                return
            # Only update health of devices in maintenance
            if self.health != Device.HEALTH_MAINTENANCE:
                return
            self.log_admin_entry(user, "%s → Unknown" % self.get_health_display())
            self.health = Device.HEALTH_UNKNOWN

        elif signal == "go_health_maintenance":
            if self.health in [Device.HEALTH_BAD, Device.HEALTH_MAINTENANCE, Device.HEALTH_RETIRED]:
                return
            self.log_admin_entry(user, "%s → Maintenance" % self.get_health_display())
            self.health = Device.HEALTH_MAINTENANCE

        elif signal == "go_health_retired":
            if self.health in [Device.HEALTH_BAD, Device.HEALTH_RETIRED]:
                return
            self.log_admin_entry(user, "%s → Retired" % self.get_health_display())
            self.health = Device.HEALTH_RETIRED

        else:
            raise NotImplementedError("Unknown signal %s" % signal)

    def load_configuration(self, job_ctx=None, output_format="dict"):
        """
        Maps the device dictionary to the static templates in /etc/.
        raise: this function can raise IOError, jinja2.TemplateError or yaml.YAMLError -
            handling these exceptions may be context-dependent, users will need
            useful messages based on these exceptions.
        """
        # The job_ctx should not be None while an empty dict is ok
        if job_ctx is None:
            job_ctx = {}

        if output_format == "raw":
            try:
                with open(os.path.join(Device.CONFIG_PATH,
                                       "%s.jinja2" % self.hostname), "r") as f_in:
                    return f_in.read()
            except IOError:
                return None

        # Create the environment
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                [Device.CONFIG_PATH,
                 os.path.join(os.path.dirname(Device.CONFIG_PATH), "device-types")]),
            trim_blocks=True)

        try:
            template = env.get_template("%s.jinja2" % self.hostname)
            device_template = template.render(**job_ctx)
        except jinja2.TemplateError:
            return None

        if output_format == "yaml":
            return device_template
        else:
            return yaml.load(device_template)

    def minimise_configuration(self, data):
        """
        Support for dynamic connections which only require
        critical elements of device configuration.
        Principally drop top level parameters and commands
        like power.
        """
        device_configuration = {
            'hostname': self.hostname,
            'constants': data['constants'],
            'timeouts': data['timeouts'],
            'actions': {
                'deploy': {
                    'methods': data['actions']['deploy']['methods']
                },
                'boot': {
                    'methods': data['actions']['boot']['methods']
                }
            }
        }
        return device_configuration

    def save_configuration(self, data):
        try:
            with open(os.path.join(self.CONFIG_PATH,
                                   "%s.jinja2" % self.hostname), "w") as f_out:
                f_out.write(data)
            return True
        except IOError as exc:
            logger = logging.getLogger("lava_scheduler_app")
            logger.error("Error saving device configuration for %s: %s",
                         self.hostname, str(exc))
            return False

    def get_extends(self):
        jinja_config = self.load_configuration(output_format="raw")
        if not jinja_config:
            return None

        env = jinja2.Environment()
        ast = env.parse(jinja_config)
        extends = list(ast.find_all(jinja2.nodes.Extends))
        if len(extends) != 1:
            logger = logging.getLogger('lava_scheduler_app')
            logger.error("Found %d extends for %s", len(extends), self.hostname)
            return None
        else:
            return os.path.splitext(extends[0].template.value)[0]

    @property
    def is_exclusive(self):
        jinja_config = self.load_configuration(output_format="raw")
        if not jinja_config:
            return False

        env = jinja2.Environment()
        ast = env.parse(jinja_config)

        for assign in ast.find_all(jinja2.nodes.Assign):
            if assign.target.name == "exclusive":
                return bool(assign.node.value)
        return False

    def get_health_check(self):
        # Do not submit any new v1 job
        if not self.is_pipeline:
            return None

        # Get the device dictionary
        extends = self.get_extends()
        if not extends:
            return None

        filename = os.path.join(Device.HEALTH_CHECK_PATH, "%s.yaml" % extends)
        # Try if health check file is having a .yml extension
        if not os.path.exists(filename):
            filename = os.path.join(Device.HEALTH_CHECK_PATH,
                                    "%s.yml" % extends)
        try:
            with open(filename, "r") as f_in:
                return f_in.read()
        except IOError:
            return None


class JobFailureTag(models.Model):
    """
    Allows us to maintain a set of common ways jobs fail. These can then be
    associated with a TestJob so we can do easy data mining
    """
    name = models.CharField(unique=True, max_length=256)

    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name


def _get_tag_list(tags, pipeline=False):
    """
    Creates a list of Tag objects for the specified device tags
    for singlenode and multinode jobs.
    :param tags: a list of strings from the JSON
    :return: a list of tags which match the strings
    :raise: JSONDataError if a tag cannot be found in the database.
    """
    taglist = []
    if not isinstance(tags, list):
        msg = "'device_tags' needs to be a list - received %s" % type(tags)
        raise yaml.YAMLError(msg) if pipeline else JSONDataError(msg)
    for tag_name in tags:
        try:
            taglist.append(Tag.objects.get(name=tag_name))
        except Tag.DoesNotExist:
            msg = "Device tag '%s' does not exist in the database." % tag_name
            raise yaml.YAMLError(msg) if pipeline else JSONDataError(msg)

    return taglist


def _check_tags(taglist, device_type=None, hostname=None):
    """
    Checks each available device against required tags
    :param taglist: list of Tag objects (not strings) for this job
    :param device_type: which types of device need to satisfy the tags -
    called during submission.
    :param hostname: check if this device can satisfy the tags - called
    from the daemon when scheduling from the queue.
    :return: a list of devices suitable for all the specified tags
    :raise: DevicesUnavailableException if no devices can satisfy the
    combination of tags.
    """
    if not device_type and not hostname:
        # programming error
        return []
    if len(taglist) == 0:
        # no tags specified in the job, any device can be used.
        return []
    q = models.Q()
    if device_type:
        q = q.__and__(models.Q(device_type=device_type))
    if hostname:
        q = q.__and__(models.Q(hostname=hostname))
    q = q.__and__(~models.Q(health=Device.HEALTH_RETIRED))
    tag_devices = set(Device.objects.filter(q))
    matched_devices = []
    for device in tag_devices:
        if set(device.tags.all()) & set(taglist) == set(taglist):
            matched_devices.append(device)
    if len(matched_devices) == 0 and device_type:
        raise DevicesUnavailableException(
            "No devices of type %s are available which have all of the tags '%s'."
            % (device_type, ", ".join([x.name for x in taglist])))
    if len(matched_devices) == 0 and hostname:
        raise DevicesUnavailableException(
            "Device %s does not support all of the tags '%s'."
            % (hostname, ", ".join([x.name for x in taglist])))
    return list(set(matched_devices))


def _check_submit_to_device(device_list, user):
    """
    Handles the affects of Device Ownership on job submission
    :param device_list: A list of device objects to check
    :param user: The user submitting the job
    :return: a subset of the device_list to which the user
    is allowed to submit a TestJob.
    :raise: DevicesUnavailableException if none of the
    devices in device_list are available for submission by this user.
    """
    allow = []
    # ensure device_list is or can be converted to a list
    # DB queries result in a RestrictedResourceQuerySet
    if not isinstance(list(device_list), list) or len(device_list) == 0:
        # logic error
        return allow
    device_type = None
    for device in device_list:
        device_type = device.device_type
        if device.health != Device.HEALTH_RETIRED and device.can_submit(user):
            allow.append(device)
    if len(allow) == 0:
        raise DevicesUnavailableException(
            "No devices of type %s are currently available to user %s"
            % (device_type, user))
    return allow


def _check_tags_support(tag_devices, device_list):
    """
    Combines the Device Ownership list with the requested tag list and
    returns any devices which meet both criteria.
    If neither the job nor the device have any tags, tag_devices will
    be empty, so the check will pass.
    :param tag_devices: A list of devices which meet the tag
    requirements
    :param device_list: A list of devices to which the user is able
    to submit a TestJob
    :raise: DevicesUnavailableException if there is no overlap between
    the two sets.
    """
    if len(tag_devices) == 0:
        # no tags requested in the job: proceed.
        return
    if len(set(tag_devices) & set(device_list)) == 0:
        raise DevicesUnavailableException(
            "Not enough devices available matching the requested tags.")


def _get_device_type(user, name):
    """
    Gets the device type for the supplied name and ensures
    the user is an owner of at least one of those devices.
    :param user: the user submitting the TestJob
    """
    logger = logging.getLogger('lava_scheduler_app')
    try:
        device_type = DeviceType.objects.get(name=name)
    except (ObjectDoesNotExist, MultipleObjectsReturned) as e:
        msg = "Device type '%s' is unavailable. %s" % (name, e)
        logger.error(msg)
        raise DevicesUnavailableException(msg)
    if not device_type.some_devices_visible_to(user):
        msg = "Device type '%s' is unavailable to user '%s'" % (name, user.username)
        logger.error(msg)
        raise DevicesUnavailableException(msg)
    return device_type


# pylint: disable=too-many-arguments,too-many-locals
def _create_pipeline_job(job_data, user, taglist, device=None,
                         device_type=None, target_group=None,
                         orig=None):

    if not isinstance(job_data, dict):
        # programming error
        raise RuntimeError("Invalid job data %s" % job_data)

    if 'connection' in job_data:
        device_type = None
    elif not device and not device_type:
        # programming error
        return None

    if not taglist:
        taglist = []

    priorities = dict([(j.upper(), i) for i, j in TestJob.PRIORITY_CHOICES])
    priority = TestJob.MEDIUM
    if 'priority' in job_data:
        priority_key = job_data['priority'].upper()
        if priority_key not in priorities:
            raise SubmissionException("Invalid job priority: %r" % priority_key)
        priority = priorities[priority_key]

    public_state = True
    visibility = TestJob.VISIBLE_PUBLIC
    viewing_groups = []
    param = job_data['visibility']
    if isinstance(param, str):
        if param == 'personal':
            public_state = False
            visibility = TestJob.VISIBLE_PERSONAL
    elif isinstance(param, dict):
        public_state = False
        if 'group' in param:
            visibility = TestJob.VISIBLE_GROUP
            known_groups = list(Group.objects.filter(name__in=param['group']))
            if not known_groups:
                raise SubmissionException(
                    "No known groups were found in the visibility list.")
            viewing_groups.extend(known_groups)

    if not orig:
        orig = yaml.dump(job_data)
    job = TestJob(definition=yaml.dump(job_data), original_definition=orig,
                  submitter=user,
                  requested_device_type=device_type,
                  target_group=target_group,
                  description=job_data['job_name'],
                  health_check=False,
                  user=user, is_public=public_state,
                  visibility=visibility,
                  priority=priority,
                  is_pipeline=True)
    job.save()
    # need a valid job before the tags can be assigned, then it needs to be saved again.
    for tag in Tag.objects.filter(name__in=taglist):
        job.tags.add(tag)

    for grp in viewing_groups:
        job.viewing_groups.add(grp)

    return job


def _pipeline_protocols(job_data, user, yaml_data=None):  # pylint: disable=too-many-locals,too-many-branches
    """
    Handle supported pipeline protocols
    Check supplied parameters and change the device selection if necessary.
    This function has two stages - calculate the device_list, create the TestJobs.
    Other protocols can affect the device_list before the jobs are created.
    role_dictionary = {  # map of the multinode group
        role: {
            'devices': [],
            'jobs': [],
            'tags': []
        }
    }

    Note: this function does *not* deal with the device state - this is a submission
    check to add the job(s) to the queue. It is not a problem if devices for this
    job are currently busy, only that there are enough devices which are not retired.
    So despite doing the tag checks here, the job is created with just the device_type
    and the checks are done again before the job starts.

    Actual device assignment happens in lava_scheduler_daemon:dbjobsource.py until
    this migrates into lava-master.

    params:
      job_data - dictionary of the submission YAML
      user: the user submitting the job
    returns:
      list of all jobs created using the specified type(s) which meet the protocol criteria,
      specified device tags and which the user is able to submit. (This is not a QuerySet,
      it is explicitly a list object.)
    exceptions:
        DevicesUnavailableException if all criteria cannot be met.
    """
    device_list = []
    if isinstance(job_data, dict) and 'protocols' not in job_data:
        return device_list

    if not yaml_data:
        yaml_data = yaml.dump(job_data)
    role_dictionary = {}  # map of the multinode group
    if 'lava-multinode' in job_data['protocols']:
        # create target_group uuid, just a label for the coordinator.
        target_group = str(uuid.uuid4())

        # Handle the requirements of the Multinode protocol
        # FIXME: needs a schema check
        # FIXME: the vland protocol will affect the device_list
        if 'roles' in job_data['protocols']['lava-multinode']:
            for role in job_data['protocols']['lava-multinode']['roles']:
                role_dictionary[role] = {
                    'devices': [],
                    'tags': []
                }
                params = job_data['protocols']['lava-multinode']['roles'][role]
                if 'device_type' in params and 'connection' in params:
                    raise SubmissionException(
                        "lava-multinode protocol cannot support device_type and connection for a single role.")
                if 'device_type' not in params and 'connection' in params:
                    # always allow support for dynamic connections which have no devices.
                    if 'host_role' not in params:
                        raise SubmissionException("connection specified without a host_role")
                    continue
                device_type = _get_device_type(user, params['device_type'])
                role_dictionary[role]['device_type'] = device_type

                allowed_devices = []
                device_list = Device.objects.filter(
                    Q(device_type=device_type), Q(is_pipeline=True), ~Q(health=Device.HEALTH_RETIRED))
                allowed_devices.extend(_check_submit_to_device(list(device_list), user))

                if len(allowed_devices) < params['count']:
                    raise DevicesUnavailableException("Not enough devices of type %s are currently "
                                                      "available to user %s"
                                                      % (device_type, user))
                role_dictionary[role]['tags'] = _get_tag_list(params.get('tags', []), True)
                if role_dictionary[role]['tags']:
                    supported = _check_tags(role_dictionary[role]['tags'], device_type=device_type)
                    _check_tags_support(supported, allowed_devices)

                # FIXME: other protocols could need to remove devices from 'supported' here

                # the device_roles cannot be set here - only once the final group has been reserved

        job_object_list = []

        # so far, just checked availability, now create the data.
        # Tags and device_type are tied to the role. The actual device is
        # a combination of the device_type and the count. Devices from the
        # supported list are allocated to jobs for the specified role.

        # split the YAML - needs the full device group information
        # returns a dict indexed by role, containing a list of jobs
        job_dictionary = utils.split_multinode_yaml(job_data, target_group)

        if not job_dictionary:
            raise SubmissionException("Unable to split multinode job submission.")

        # structural changes done, now create the testjob.
        parent = None  # track the zero id job as the parent of the group in the sub_id text field
        for role, role_dict in role_dictionary.items():
            for node_data in job_dictionary[role]:
                job = _create_pipeline_job(
                    node_data, user, target_group=target_group,
                    taglist=role_dict['tags'],
                    device_type=role_dict.get('device_type', None),
                    orig=None  # store the dump of the split yaml as the job definition
                )
                if not job:
                    raise SubmissionException("Unable to create job for %s" % node_data)
                if not parent:
                    parent = job.id
                job.sub_id = "%d.%d" % (parent, node_data['protocols']['lava-multinode']['sub_id'])
                job.multinode_definition = yaml_data  # store complete submisison, inc. comments
                job.save()
                job_object_list.append(job)

        return job_object_list


class TestJob(RestrictedResource):
    """
    A test job is a test process that will be run on a Device.
    """
    class Meta:
        index_together = ["health", "state", "requested_device_type"]

    objects = RestrictedResourceManager.from_queryset(
        RestrictedTestJobQuerySet)()

    # VISIBILITY levels are subject to any device restrictions and hidden device type rules
    VISIBLE_PUBLIC = 0  # anyone can view, submit or resubmit
    VISIBLE_PERSONAL = 1  # only the submitter can view, submit or resubmit
    VISIBLE_GROUP = 2  # A single group is specified, all users in that group (and that group only) can view.

    VISIBLE_CHOICES = (
        (VISIBLE_PUBLIC, 'Publicly visible'),  # publicly and publically are equivalent meaning
        (VISIBLE_PERSONAL, 'Personal only'),
        (VISIBLE_GROUP, 'Group only'),
    )

    NOTIFY_EMAIL_METHOD = 'email'
    NOTIFY_IRC_METHOD = 'irc'

    id = models.AutoField(primary_key=True)

    sub_id = models.CharField(
        verbose_name=_(u"Sub ID"),
        blank=True,
        max_length=200
    )

    target_group = models.CharField(
        verbose_name=_(u"Target Group"),
        blank=True,
        max_length=64,
        null=True,
        default=None
    )

    submitter = models.ForeignKey(
        User,
        verbose_name=_(u"Submitter"),
        related_name='+',
    )

    visibility = models.IntegerField(
        verbose_name=_(u'Visibility type'),
        help_text=_(u'Visibility affects the TestJob and all results arising from that job, '
                    u'including Queries and Reports.'),
        choices=VISIBLE_CHOICES,
        default=VISIBLE_PUBLIC,
        editable=True
    )

    viewing_groups = models.ManyToManyField(
        # functionally, may be restricted to only one group at a time
        # depending on implementation complexity
        Group,
        verbose_name=_(u'Viewing groups'),
        help_text=_(u'Adding groups to an intersection of groups reduces visibility.'
                    u'Adding groups to a union of groups expands visibility.'),
        related_name='viewing_groups',
        blank=True,
        default=None,
        editable=True
    )

    description = models.CharField(
        verbose_name=_(u"Description"),
        max_length=200,
        null=True,
        blank=True,
        default=None
    )

    health_check = models.BooleanField(default=False)

    # Only one of requested_device_type or dynamic_connection should be
    # non-null. Dynamic connections have no device.
    requested_device_type = models.ForeignKey(
        DeviceType, null=True, default=None, related_name='+', blank=True)

    @property
    def dynamic_connection(self):
        """
        Secondary connection detection - pipeline & multinode only.
        (Enhanced version of vmgroups.)
        A Primary connection needs a real device (persistence).
        """
        if not self.is_pipeline or not self.is_multinode or not self.definition:
            return False
        job_data = yaml.load(self.definition)
        return 'connection' in job_data

    tags = models.ManyToManyField(Tag, blank=True)

    # This is set once the job starts or is reserved.
    actual_device = models.ForeignKey(
        Device, null=True, default=None, related_name='testjobs', blank=True)

    submit_time = models.DateTimeField(
        verbose_name=_(u"Submit time"),
        auto_now=False,
        auto_now_add=True,
        db_index=True
    )
    start_time = models.DateTimeField(
        verbose_name=_(u"Start time"),
        auto_now=False,
        auto_now_add=False,
        null=True,
        blank=True,
        editable=False
    )
    end_time = models.DateTimeField(
        verbose_name=_(u"End time"),
        auto_now=False,
        auto_now_add=False,
        null=True,
        blank=True,
        editable=False
    )

    @property
    def duration(self):
        if self.end_time is None or self.start_time is None:
            return None
        return self.end_time - self.start_time

    STATE_SUBMITTED, STATE_SCHEDULING, STATE_SCHEDULED, STATE_RUNNING, STATE_CANCELING, STATE_FINISHED = range(6)
    STATE_CHOICES = (
        (STATE_SUBMITTED, "Submitted"),
        (STATE_SCHEDULING, "Scheduling"),
        (STATE_SCHEDULED, "Scheduled"),
        (STATE_RUNNING, "Running"),
        (STATE_CANCELING, "Canceling"),
        (STATE_FINISHED, "Finished"),
    )
    state = models.IntegerField(choices=STATE_CHOICES,
                                default=STATE_SUBMITTED,
                                editable=False)

    HEALTH_UNKNOWN, HEALTH_COMPLETE, HEALTH_INCOMPLETE, HEALTH_CANCELED = range(4)
    HEALTH_CHOICES = (
        (HEALTH_UNKNOWN, "Unknown"),
        (HEALTH_COMPLETE, "Complete"),
        (HEALTH_INCOMPLETE, "Incomplete"),
        (HEALTH_CANCELED, "Canceled"),
    )
    health = models.IntegerField(choices=HEALTH_CHOICES,
                                 default=HEALTH_UNKNOWN)

    def go_state_scheduling(self, device):
        """
        Used for multinode jobs when all jobs are not scheduled yet.
        When each sub jobs are scheduled, the state is change to
        STATE_SCHEDULED
        Jobs that are not multinode will directly use STATE_SCHEDULED
        """
        if device.state != Device.STATE_IDLE:
            raise Exception("device is not IDLE")
        if self.state >= TestJob.STATE_SCHEDULING:
            return
        self.state = TestJob.STATE_SCHEDULING
        # TODO: check that device is locked
        self.actual_device = device
        self.actual_device.testjob_signal("go_state_scheduling", self)
        self.actual_device.save()

    def go_state_scheduled(self, device=None):
        """
        The jobs has been scheduled or the given device.
        lava-master will send a START to the right lava-slave.
        """
        dynamic_connection = self.dynamic_connection
        if device is None:
            # dynamic connection does not have any device
            if not dynamic_connection:
                if self.actual_device is None:
                    raise Exception("actual_device is not set")
                device = self.actual_device
        else:
            if device.state != Device.STATE_IDLE:
                raise Exception("device is not IDLE")
        if self.state >= TestJob.STATE_SCHEDULED:
            return
        self.state = TestJob.STATE_SCHEDULED
        # dynamic connection does not have any device
        if not dynamic_connection:
            # TODO: check that device is locked
            self.actual_device = device
            self.actual_device.testjob_signal("go_state_scheduled", self)
            self.actual_device.save()

    def go_state_running(self):
        """
        lava-master received a START_OK for this job which is now running.
        """
        if self.state >= TestJob.STATE_RUNNING:
            return
        self.state = TestJob.STATE_RUNNING
        self.start_time = timezone.now()
        # TODO: check that self.actual_device is locked by the
        # select_for_update on the TestJob
        if not self.dynamic_connection:
            self.actual_device.testjob_signal("go_state_running", self)
            self.actual_device.save()

    def go_state_canceling(self, sub_cancel=False):
        """
        The job was canceled by a user. lava-master will send a CANCEL to the right lava-slave.
        """
        if self.state >= TestJob.STATE_CANCELING:
            return
        # If the job was not scheduled, go directly to STATE_FINISHED
        if self.state == TestJob.STATE_SUBMITTED:
            self.go_state_finished(TestJob.HEALTH_CANCELED)
            return

        self.state = TestJob.STATE_CANCELING
        # TODO: check that self.actual_device is locked by the
        # select_for_update on the TestJob
        if not self.dynamic_connection:
            self.actual_device.testjob_signal("go_state_canceling", self)
            self.actual_device.save()

        # For multinode, cancel all sub jobs if the current job is essential
        if not sub_cancel and self.essential_role:
            for sub_job in self.sub_jobs_list:
                if sub_job != self:
                    sub_job.go_state_canceling(sub_cancel=True)
                    sub_job.save()

    def go_state_finished(self, health):
        """
        The job has been terminated by either lava-master or lava-logs. The
        job health can be set.
        """
        if self.state == TestJob.STATE_FINISHED:
            return

        if health == TestJob.HEALTH_UNKNOWN:
            raise Exception("Cannot give HEALTH_UNKNOWN")

        # If the job was in STATE_CANCELING, then override health
        self.health = health
        if self.state == TestJob.STATE_CANCELING:
            self.health = TestJob.HEALTH_CANCELED
        self.state = TestJob.STATE_FINISHED

        self.end_time = timezone.now()
        # TODO: check that self.actual_device is locked by the
        # select_for_update on the TestJob
        # Skip non-scheduled jobs and dynamic_connections
        if self.actual_device is not None:
            self.actual_device.testjob_signal("go_state_finished", self)
            self.actual_device.save()

        # For multinode, cancel all sub jobs if the current job is essential
        # and it was a failure.
        if health == TestJob.HEALTH_INCOMPLETE and self.essential_role:
            for sub_job in self.sub_jobs_list:
                if sub_job != self:
                    sub_job.go_state_canceling(sub_cancel=True)
                    sub_job.save()

    LOW, MEDIUM, HIGH = (0, 50, 100)
    PRIORITY_CHOICES = (
        (LOW, 'Low'),
        (MEDIUM, 'Medium'),
        (HIGH, 'High'),
    )
    priority = models.IntegerField(
        choices=PRIORITY_CHOICES,
        default=MEDIUM,
        verbose_name=_(u"Priority"),
    )

    definition = models.TextField(
        editable=False,
    )

    original_definition = models.TextField(
        editable=False,
        blank=True
    )

    multinode_definition = models.TextField(
        editable=False,
        blank=True
    )

    is_pipeline = models.BooleanField(
        verbose_name="Pipeline job?",
        default=False,
        editable=False
    )

    # calculated by the master validation process.
    pipeline_compatibility = models.IntegerField(
        default=0,
        editable=False
    )

    # only one value can be set as there is only one opportunity
    # to transition a device from Running to Offlining.
    admin_notifications = models.TextField(
        editable=False,
        blank=True
    )

    @property
    def size_limit(self):
        return settings.LOG_SIZE_LIMIT * 1024 * 1024

    @property
    def output_dir(self):
        # Fallback to the old path if it does exist
        old_path = os.path.join(settings.MEDIA_ROOT, 'job-output',
                                'job-%s' % self.id)
        if os.path.exists(old_path):
            return old_path
        return os.path.join(settings.MEDIA_ROOT, 'job-output',
                            "%02d" % self.submit_time.year,
                            "%02d" % self.submit_time.month,
                            "%02d" % self.submit_time.day,
                            str(self.id))

    def output_file(self):
        filename = 'output.yaml' if self.is_pipeline else 'output.txt'
        output_path = os.path.join(self.output_dir, filename)
        if os.path.exists(output_path):
            return open(output_path, encoding='utf-8', errors='replace')
        else:
            return None

    def archived_job_file(self):
        """Checks if the current job's log output file was archived.
        """
        last_info = os.path.join(settings.ARCHIVE_ROOT, 'job-output',
                                 'last.info')

        if not os.path.exists(last_info):
            return False

        with open(last_info, 'r') as last:
            last_archived_job = int(last.read())

        return self.id <= last_archived_job

    failure_tags = models.ManyToManyField(
        JobFailureTag, blank=True, related_name='failure_tags')
    failure_comment = models.TextField(null=True, blank=True)

    _results_link = models.CharField(
        max_length=400, default=None, null=True, blank=True, db_column="results_link")

    @property
    def results_link(self):
        if self.is_pipeline:
            return u'/results/%s' % self.id
        else:
            return None

    @property
    def essential_role(self):  # pylint: disable=too-many-return-statements
        if not self.is_multinode:
            return False
        data = yaml.load(self.definition)
        # would be nice to use reduce here but raising and catching TypeError is slower
        # than checking 'if .. in ' - most jobs will return False.
        if 'protocols' not in data:
            return False
        if 'lava-multinode' not in data['protocols']:
            return False
        if 'role' not in data['protocols']['lava-multinode']:
            return False
        if 'essential' not in data['protocols']['lava-multinode']:
            return False
        return data['protocols']['lava-multinode']['essential']

    @property
    def device_role(self):  # pylint: disable=too-many-return-statements
        if not self.is_multinode:
            return "Error"
        data = yaml.load(self.definition)
        if 'protocols' not in data:
            return 'Error'
        if 'lava-multinode' not in data['protocols']:
            return 'Error'
        if 'role' not in data['protocols']['lava-multinode']:
            return 'Error'
        return data['protocols']['lava-multinode']['role']

    def __str__(self):
        job_type = 'health_check' if self.health_check else 'test'
        r = "%s (%s) %s job" % (self.get_state_display(), self.get_health_display(), job_type)
        if self.actual_device:
            r += " on %s" % (self.actual_device.hostname)
        else:
            if self.requested_device_type:
                r += " for %s" % (self.requested_device_type.name)
        r += " (%d)" % (self.id)
        return r

    @models.permalink
    def get_absolute_url(self):
        return ("lava.scheduler.job.detail", [self.display_id])

    @classmethod
    def from_yaml_and_user(cls, yaml_data, user, original_job=None):
        """
        Runs the submission checks on incoming pipeline jobs.
        Either rejects the job with a DevicesUnavailableException (which the caller is expected to handle), or
        creates a TestJob object for the submission and saves that testjob into the database.
        This function must *never* be involved in setting the state of this job or the state of any associated device.
        Retains yaml_data as the original definition to retain comments.

        :return: a single TestJob object or a list
        (explicitly, a list, not a QuerySet) of evaluated TestJob objects
        """
        job_data = yaml.load(yaml_data)

        # Unpack include value if present.
        job_data = handle_include_option(job_data)

        # visibility checks
        if 'visibility' not in job_data:
            raise SubmissionException("Job visibility must be specified.")
            # handle view and admin users and groups

        # pipeline protocol handling, e.g. lava-multinode
        job_list = _pipeline_protocols(job_data, user, yaml_data)
        if job_list:
            # explicitly a list, not a QuerySet.
            return job_list
        # singlenode only
        device_type = _get_device_type(user, job_data['device_type'])
        allow = _check_submit_to_device(list(Device.objects.filter(
            device_type=device_type, is_pipeline=True)), user)
        if not allow:
            raise DevicesUnavailableException("No devices of type %s have pipeline support." % device_type)
        taglist = _get_tag_list(job_data.get('tags', []), True)
        if taglist:
            supported = _check_tags(taglist, device_type=device_type)
            _check_tags_support(supported, allow)
        if original_job and original_job.is_pipeline:
            # Add old job absolute url to metadata for pipeline jobs.
            job_url = str(original_job.get_absolute_url())
            try:
                site = Site.objects.get_current()
            except (Site.DoesNotExist, ImproperlyConfigured):
                pass
            else:
                job_url = "http://%s%s" % (site.domain, job_url)

            job_data.setdefault("metadata", {}).setdefault("job.original", job_url)

        return _create_pipeline_job(job_data, user, taglist, device=None, device_type=device_type, orig=yaml_data)

    def clean(self):
        """
        Implement the schema constraints for visibility for pipeline jobs so that
        admins cannot set a job into a logically inconsistent state.
        """
        if self.is_pipeline:
            # public settings must match
            if self.is_public and self.visibility != TestJob.VISIBLE_PUBLIC:
                raise ValidationError("is_public is set but visibility is not public.")
            elif not self.is_public and self.visibility == TestJob.VISIBLE_PUBLIC:
                raise ValidationError("is_public is not set but visibility is public.")
        else:
            if self.visibility != TestJob.VISIBLE_PUBLIC:
                raise ValidationError("Only pipeline jobs support any value of visibility except the default "
                                      "PUBLIC, even if the job and bundle are private.")
        return super(TestJob, self).clean()

    def can_view(self, user):
        """
        Take over the checks behind RestrictedIDLinkColumn, for
        pipeline jobs which support a view user list or view group.
        For speed, the lookups on the user/group tables are only by id
        Any elements which would need admin access must be checked
        separately using can_admin instead.
        :param user:  the user making the request
        :return: True or False
        """
        if self._can_admin(user, resubmit=False):
            return True
        device_type = self.job_device_type()
        if device_type and device_type.owners_only:
            if not device_type.some_devices_visible_to(user):
                return False
        if self.is_public:
            return True
        if not self.is_pipeline:
            # old jobs will be private, only pipeline extends beyond this level
            return self.is_accessible_by(user)
        logger = logging.getLogger('lava_scheduler_app')
        if self.visibility == self.VISIBLE_PUBLIC:
            # logical error
            logger.exception("job [%s] visibility is public but job is not public.", self.id)
        elif self.visibility == self.VISIBLE_PERSONAL:
            return user == self.submitter
        elif self.visibility == self.VISIBLE_GROUP:
            # The user should be member of every groups
            user_groups = user.groups.all()
            return all([g in user_groups for g in self.viewing_groups.all()])

        return False

    def _can_admin(self, user, resubmit=True):
        """
        used to check for things like if the user can cancel or annotate
        a job failure.
        Failure to allow admin access returns HIDE_ACCESS or DENY_ACCESS
        For speed, the lookups on the user/group tables are only by id
        :param user:  the user making the request
        :param resubmit: if this check should also consider resumbit/cancel permission
        :return: access level, up to a maximum of FULL_ACCESS
        """
        # FIXME: move resubmit permission check to a separate function & rationalise.
        owner = False
        if self.actual_device is not None:
            owner = self.actual_device.can_admin(user)
        perm = user.is_superuser or user == self.submitter or owner
        if resubmit:
            perm = user.is_superuser or user == self.submitter or owner or\
                user.has_perm('lava_scheduler_app.cancel_resubmit_testjob')
        return perm

    def can_change_priority(self, user):
        """
        Permission and state required to change job priority.
        Multinode jobs cannot have their priority changed.
        """
        return (user.is_superuser or user == self.submitter or
                user.has_perm('lava_scheduler_app.cancel_resubmit_testjob'))

    def can_annotate(self, user):
        """
        Permission required for user to add failure information to a job
        """
        return self._can_admin(user) and self.state == TestJob.STATE_FINISHED

    def can_cancel(self, user):
        states = [TestJob.STATE_SUBMITTED, TestJob.STATE_RUNNING]
        return self._can_admin(user) and self.state in states

    def can_resubmit(self, user):
        return self.is_pipeline and \
            (user.is_superuser or
             user.has_perm('lava_scheduler_app.cancel_resubmit_testjob'))

    def job_device_type(self):
        device_type = None
        if self.actual_device:
            device_type = self.actual_device.device_type
        elif self.requested_device_type:
            device_type = self.requested_device_type
        return device_type

    def _generate_summary_mail(self):
        domain = '???'
        try:
            site = Site.objects.get_current()
        except (Site.DoesNotExist, ImproperlyConfigured):
            pass
        else:
            domain = site.domain
        url_prefix = 'http://%s' % domain
        return render_to_string(
            'lava_scheduler_app/job_summary_mail.txt',
            {'job': self, 'url_prefix': url_prefix})

    def _generate_cancellation_mail(self, user):
        domain = '???'
        try:
            site = Site.objects.get_current()
        except (Site.DoesNotExist, ImproperlyConfigured):
            pass
        else:
            domain = site.domain
        url_prefix = 'http://%s' % domain
        return render_to_string(
            'lava_scheduler_app/job_cancelled_mail.txt',
            {'job': self, 'url_prefix': url_prefix, 'user': user})

    def _send_cancellation_mail(self, user):
        if user == self.submitter:
            return
        recipient = get_object_or_404(User.objects.select_related(), id=self.submitter.id)
        if not recipient.email:
            return
        mail = self._generate_cancellation_mail(user)
        description = self.description.splitlines()[0]
        if len(description) > 200:
            description = description[197:] + '...'
        logger = logging.getLogger('lava_scheduler_app')
        logger.info("sending mail to %s", recipient.email)
        try:
            send_mail(
                "LAVA job notification: " + description, mail,
                settings.SERVER_EMAIL, [recipient.email])
        except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused, socket.error):
            logger.info("unable to send email to recipient")

    def _get_notification_recipients(self):
        job_data = simplejson.loads(self.definition)
        recipients = job_data.get('notify', [])
        recipients.extend([self.admin_notifications])  # Bug 170
        recipients = filter(None, recipients)
        if self.health != self.HEALTH_COMPLETE:
            recipients.extend(job_data.get('notify_on_incomplete', []))
        return recipients

    def send_summary_mails(self):
        recipients = self._get_notification_recipients()
        if not recipients:
            return
        mail = self._generate_summary_mail()
        description = self.description.splitlines()[0]
        if len(description) > 200:
            description = description[197:] + '...'
        logger = logging.getLogger('lava_scheduler_app')
        logger.info("sending mail to %s", recipients)
        try:
            send_mail(
                "LAVA job notification: " + description, mail,
                settings.SERVER_EMAIL, recipients)
        except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused, socket.error):
            logger.info("unable to send email - recipient refused")

    def set_failure_comment(self, message):
        if not self.failure_comment:
            self.failure_comment = message
        elif message not in self.failure_comment:
            self.failure_comment += message
        else:
            return
        self.save(update_fields=['failure_comment'])

    @property
    def sub_jobs_list(self):
        if self.is_multinode:
            jobs = TestJob.objects.filter(
                target_group=self.target_group).order_by('id')
            return jobs
        else:
            return []

    @property
    def is_multinode(self):
        return bool(self.target_group)

    @property
    def lookup_worker(self):
        if not self.is_multinode:
            return None
        try:
            data = yaml.load(self.definition)
        except yaml.YAMLError:
            return None
        if 'host_role' not in data:
            return None
        parent = None
        # the protocol requires a count of 1 for any role specified as a host_role
        for worker_job in self.sub_jobs_list:
            if worker_job.device_role == data['host_role']:
                parent = worker_job
                break
        if not parent or not parent.actual_device:
            return None
        return parent.actual_device.worker_host

    @property
    def display_id(self):
        if self.sub_id:
            return self.sub_id
        else:
            return self.id

    @classmethod
    def get_by_job_number(cls, job_id, for_update=False):
        """If JOB_ID is of the form x.y ie., a multinode job notation, then
        query the database with sub_id and get the JOB object else use the
        given id as the primary key value.

        Returns JOB object.
        """
        query = TestJob.objects
        if for_update:
            query = query.select_for_update()
        if '.' in str(job_id):
            job = query.get(sub_id=job_id)
        else:
            job = query.get(pk=job_id)
        return job

    @property
    def display_definition(self):
        """If ORIGINAL_DEFINITION is stored in the database return it, for jobs
        which do not have ORIGINAL_DEFINITION ie., jobs that were submitted
        before this attribute was introduced, return the DEFINITION.
        """
        if self.original_definition and not self.is_multinode:
            return self.original_definition
        else:
            return self.definition

    def get_passfail_results(self):
        # Get pass fail results per lava_results_app.testsuite.
        results = {}
        from lava_results_app.models import TestCase
        for suite in self.testsuite_set.all():
            results[suite.name] = {
                'pass': suite.testcase_set.filter(
                    result=TestCase.RESULT_MAP['pass']).count(),
                'fail': suite.testcase_set.filter(
                    result=TestCase.RESULT_MAP['fail']).count(),
                'skip': suite.testcase_set.filter(
                    result=TestCase.RESULT_MAP['skip']).count(),
                'unknown': suite.testcase_set.filter(
                    result=TestCase.RESULT_MAP['unknown']).count()
            }
        return results

    def get_measurement_results(self):
        # Get measurement values per lava_results_app.testcase.
        # TODO: add min, max
        from lava_results_app.models import TestSuite, TestCase

        results = {}
        for suite in TestSuite.objects.filter(job=self).prefetch_related(
                'testcase_set').annotate(
                    test_case_avg=models.Avg('testcase__measurement')):
            if suite.name not in results:
                results[suite.name] = {}
            results[suite.name]['measurement'] = suite.test_case_avg
            results[suite.name]['fail'] = suite.testcase_set.filter(
                result=TestCase.RESULT_MAP['fail']).count()

        return results

    def get_attribute_results(self, attributes):
        # Get attribute values per lava_scheduler_app.testjob.
        results = {}
        attributes = [x.strip() for x in attributes.split(',')]

        from lava_results_app.models import TestData
        testdata = TestData.objects.filter(testjob=self).first()
        if testdata:
            for attr in testdata.attributes.all():
                if attr.name in attributes:
                    results[attr.name] = {}
                    results[attr.name]['fail'] = self.health != self.HEALTH_COMPLETE
                    try:
                        results[attr.name]['value'] = float(attr.value)
                    except ValueError:
                        # Ignore non-float metadata.
                        del results[attr.name]

        return results

    def get_end_datetime(self):
        return self.end_time

    def get_xaxis_attribute(self, xaxis_attribute=None):

        from lava_results_app.models import NamedTestAttribute, TestData
        attribute = None
        if xaxis_attribute:
            try:
                testdata = TestData.objects.filter(testjob=self).first()
                if testdata:
                    attribute = NamedTestAttribute.objects.filter(
                        content_type=ContentType.objects.get_for_model(
                            TestData),
                        object_id=testdata.id,
                        name=xaxis_attribute).values_list('value', flat=True)[0]

            # FIXME: bare except
            except:  # There's no attribute, skip this result.
                pass

        return attribute

    def get_metadata_dict(self):

        from lava_results_app.models import TestData
        retval = []
        data = TestData.objects.filter(testjob=self)
        for datum in data:
            for attribute in datum.attributes.all():
                retval.append({attribute.name: attribute.value})
        return retval

    def get_token_from_description(self, description):
        from linaro_django_xmlrpc.models import AuthToken
        tokens = AuthToken.objects.filter(user=self.submitter, description=description)
        if tokens:
            return tokens.first().secret
        return description

    def create_notification(self, notify_data):
        # Create notification object.
        notification = Notification()

        if "verbosity" in notify_data:
            notification.verbosity = Notification.VERBOSITY_MAP[
                notify_data["verbosity"]]

        if "callback" in notify_data:
            notification.callback_url = self.substitute_callback_url_variables(
                notify_data["callback"]["url"])
            if notify_data["callback"].get("token", None):
                notification.callback_token = self.get_token_from_description(notify_data["callback"]['token'])
            notification.callback_method = Notification.METHOD_MAP[
                notify_data["callback"].get("method", "GET")]
            notification.callback_dataset = Notification.DATASET_MAP[
                notify_data["callback"].get("dataset", "minimal")]
            notification.callback_content_type = Notification.CONTENT_TYPE_MAP[
                notify_data['callback'].get('content-type', 'urlencoded')]

        if "type" in notify_data["criteria"]:
            notification.type = Notification.TYPE_MAP[
                notify_data["criteria"]["type"]]
        if "compare" in notify_data:
            if "blacklist" in notify_data["compare"]:
                notification.blacklist = notify_data["compare"]["blacklist"]
            if "query" in notify_data["compare"]:
                from lava_results_app.models import Query
                query_data = notify_data["compare"]["query"]
                if "username" in query_data:
                    # DoesNotExist scenario already verified in validate
                    notification.query_owner = User.objects.get(
                        username=query_data["username"])
                    notification.query_name = query_data["name"]
                else:  # Custom query.
                    notification.entity = Query.get_content_type(
                        query_data["entity"])
                    if "conditions" in query_data:
                        # Save conditions as a string.
                        notification.conditions = Query.CONDITIONS_SEPARATOR.join(['%s%s%s' % (key, Query.CONDITION_DIVIDER, value) for (key, value) in query_data["conditions"].items()])

        notification.test_job = self
        notification.template = Notification.DEFAULT_TEMPLATE
        notification.save()

        if "recipients" in notify_data:
            for recipient in notify_data["recipients"]:
                notification_recipient = NotificationRecipient(
                    notification=notification)
                notification_recipient.method = NotificationRecipient.METHOD_MAP[recipient["to"]["method"]]
                if "user" in recipient["to"]:
                    user = User.objects.get(
                        username=recipient["to"]["user"])
                    notification_recipient.user = user
                if "email" in recipient["to"]:
                    notification_recipient.email = recipient["to"]["email"]
                if "handle" in recipient["to"]:
                    notification_recipient.irc_handle = recipient["to"][
                        "handle"]
                if "server" in recipient["to"]:
                    notification_recipient.irc_server = recipient["to"][
                        "server"]

                try:
                    notification_recipient.save()
                except IntegrityError:
                    # Ignore unique constraint violation.
                    pass

        else:
            if "callback" not in notify_data:
                try:
                    notification_recipient = NotificationRecipient.objects.create(
                        user=self.submitter,
                        notification=notification)
                except IntegrityError:
                    # Ignore unique constraint violation.
                    pass

    def send_notifications(self):
        logger = logging.getLogger('lava_scheduler_app')
        notification = self.notification
        # Prep template args.
        kwargs = self.get_notification_args()
        # Process notification callback.
        notification.invoke_callback()

        for recipient in notification.notificationrecipient_set.all():
            if recipient.method == NotificationRecipient.EMAIL:
                if recipient.status == NotificationRecipient.NOT_SENT:
                    try:
                        logger.info("[%d] sending email notification to %s",
                                    self.id, recipient.email_address)
                        title = "LAVA notification for Test Job %s" % self.id
                        kwargs["user"] = self.get_recipient_args(recipient)
                        body = self.create_notification_body(
                            notification.template, **kwargs)
                        result = send_mail(
                            title, body, settings.SERVER_EMAIL,
                            [recipient.email_address])
                        if result:
                            recipient.status = NotificationRecipient.SENT
                            recipient.save()
                    except (smtplib.SMTPRecipientsRefused, jinja2.exceptions.TemplateError,
                            smtplib.SMTPSenderRefused, socket.error) as exc:
                        logger.exception(exc)
                        logger.warning("[%d] failed to send email notification to %s",
                                       self.id, recipient.email_address)
            else:  # IRC method
                if recipient.status == NotificationRecipient.NOT_SENT:
                    if recipient.irc_server_name:

                        logger.info("[%d] sending IRC notification to %s on %s",
                                    self.id, recipient.irc_handle_name,
                                    recipient.irc_server_name)
                        try:
                            irc_message = self.create_irc_notification()
                            utils.send_irc_notification(
                                Notification.DEFAULT_IRC_HANDLE,
                                recipient=recipient.irc_handle_name,
                                message=irc_message,
                                server=recipient.irc_server_name)
                            recipient.status = NotificationRecipient.SENT
                            recipient.save()
                            logger.info("[%d] IRC notification sent to %s",
                                        self.id, recipient.irc_handle_name)
                        # FIXME: this bare except should be constrained
                        except Exception as e:
                            logger.warning(
                                "[%d] IRC notification not sent. Reason: %s - %s",
                                self.id, e.__class__.__name__, str(e))

    def create_irc_notification(self):
        kwargs = {}
        kwargs["job"] = self
        kwargs["url_prefix"] = "http://%s" % utils.get_domain()
        return self.create_notification_body(
            Notification.DEFAULT_IRC_TEMPLATE, **kwargs)

    def get_notification_args(self):
        kwargs = {}
        kwargs["job"] = self
        kwargs["url_prefix"] = "http://%s" % utils.get_domain()
        kwargs["query"] = {}
        if self.notification.query_name or self.notification.entity:
            kwargs["query"]["results"] = self.notification.get_query_results()
            kwargs["query"]["link"] = self.notification.get_query_link()
            # Find the first job which has health HEALTH_COMPLETE and is not the
            # current job (this can happen with custom queries) for comparison.
            compare_index = None
            for index, result in enumerate(kwargs["query"]["results"]):
                if result.health == TestJob.HEALTH_COMPLETE and \
                   self != result:
                    compare_index = index
                    break

            kwargs["query"]["compare_index"] = compare_index
            if compare_index is not None and self.notification.blacklist:
                # Get testsuites diffs between current job and latest complete
                # job from query.
                new_suites = self.testsuite_set.all().exclude(
                    name__in=self.notification.blacklist)
                old_suites = kwargs["query"]["results"][
                    compare_index].testsuite_set.all().exclude(
                        name__in=self.notification.blacklist)
                left_suites_diff = new_suites.exclude(
                    name__in=old_suites.values_list(
                        'name', flat=True))
                right_suites_diff = old_suites.exclude(
                    name__in=new_suites.values_list('name', flat=True))

                kwargs["query"]["left_suites_diff"] = left_suites_diff
                kwargs["query"]["right_suites_diff"] = right_suites_diff

                # Get testcases diffs between current job and latest complete
                # job from query.
                from lava_results_app.models import TestCase, TestSuite
                new_cases = TestCase.objects.filter(suite__job=self).exclude(
                    name__in=self.notification.blacklist).exclude(
                        suite__name__in=self.notification.blacklist)
                old_cases = TestCase.objects.filter(suite__job=kwargs["query"]["results"][compare_index]).exclude(
                    name__in=self.notification.blacklist).exclude(
                        suite__name__in=self.notification.blacklist)

                left_cases_diff = new_cases.exclude(
                    name__in=old_cases.values_list(
                        'name', flat=True))
                right_cases_diff = old_cases.exclude(
                    name__in=new_cases.values_list('name', flat=True))

                kwargs["query"]["left_cases_diff"] = left_cases_diff
                kwargs["query"]["right_cases_diff"] = right_cases_diff

                left_suites_intersection = new_suites.filter(
                    name__in=old_suites.values_list(
                        'name', flat=True))

                # Format results.
                left_suites_count = {}
                for suite in left_suites_intersection:
                    left_suites_count[suite.name] = (
                        suite.testcase_set.filter(
                            result=TestCase.RESULT_PASS).count(),
                        suite.testcase_set.filter(
                            result=TestCase.RESULT_FAIL).count(),
                        suite.testcase_set.filter(
                            result=TestCase.RESULT_SKIP).count()
                    )

                right_suites_intersection = old_suites.filter(
                    name__in=new_suites.values_list(
                        'name', flat=True))

                # Format results.
                right_suites_count = {}
                for suite in right_suites_intersection:
                    right_suites_count[suite.name] = (
                        suite.testcase_set.filter(
                            result=TestCase.RESULT_PASS).count(),
                        suite.testcase_set.filter(
                            result=TestCase.RESULT_FAIL).count(),
                        suite.testcase_set.filter(
                            result=TestCase.RESULT_SKIP).count()
                    )

                kwargs["query"]["left_suites_count"] = left_suites_count
                kwargs["query"]["right_suites_count"] = right_suites_count

                # Format {<Testcase>: old_result, ...}
                testcases_changed = {}
                for suite in left_suites_intersection:
                    try:
                        old_suite = TestSuite.objects.get(
                            name=suite.name,
                            job=kwargs["query"]["results"][compare_index])
                    except TestSuite.DoesNotExist:
                        continue  # No matching suite, move on.
                    for testcase in suite.testcase_set.all():
                        try:
                            old_testcase = TestCase.objects.get(
                                suite=old_suite, name=testcase.name)
                            if old_testcase and \
                               testcase.result != old_testcase.result:
                                testcases_changed[testcase] = old_testcase.get_result_display()
                        except TestCase.DoesNotExist:
                            continue  # No matching TestCase, move on.
                        except TestCase.MultipleObjectsReturned:
                            logging.info("Multiple Test Cases with the equal name in TestSuite %s, could not compare",
                                         old_suite)

                kwargs["query"]["testcases_changed"] = testcases_changed

        return kwargs

    def get_recipient_args(self, recipient):
        user_data = {}
        if recipient.user:
            user_data["username"] = recipient.user.username
            user_data["first_name"] = recipient.user.first_name
            user_data["last_name"] = recipient.user.last_name
        return user_data

    def create_notification_body(self, template_name, **kwargs):
        txt_body = u""
        txt_body = Notification.TEMPLATES_ENV.get_template(
            template_name).render(**kwargs)
        return txt_body

    def notification_criteria(self, criteria, old_job):
        # support special status of finished, otherwise skip to normal
        if criteria["status"] == "finished":
            return self.state == TestJob.STATE_FINISHED

        if criteria["status"] == "running":
            return self.state == TestJob.STATE_RUNNING

        if criteria["status"] == "complete":
            const = TestJob.HEALTH_COMPLETE
        elif criteria["status"] == "incomplete":
            const = TestJob.HEALTH_INCOMPLETE
        else:
            const = TestJob.HEALTH_CANCELED

        # use normal notification support
        if self.health == const:
            if "type" in criteria:
                if criteria["type"] == "regression":
                    if old_job.health == TestJob.HEALTH_COMPLETE and \
                       self.health == TestJob.HEALTH_INCOMPLETE:
                        return True
                if criteria["type"] == "progression":
                    if old_job.health == TestJob.HEALTH_INCOMPLETE and \
                       self.health == TestJob.HEALTH_COMPLETE:
                        return True
            else:
                return True

        return False

    def substitute_callback_url_variables(self, callback_url):
        # Substitute variables in callback_url with field values from self.
        # Format: { FIELD_NAME }
        # If field name is non-existing, return None.
        logger = logging.getLogger('lava_scheduler_app')

        substitutes = re.findall(r'{\s*[A-Z_-]*\s*}', callback_url)
        for sub in substitutes:

            attribute_name = sub.replace('{', '').replace('}', '').strip().lower()
            try:
                attr = getattr(self, attribute_name)
            except AttributeError:
                logger.error("Attribute '%s' does not exist in TestJob." % attribute_name)
                continue

            callback_url = callback_url.replace(str(sub), str(attr))

        return callback_url


class Notification(models.Model):

    TEMPLATES_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "templates/",
        TestJob._meta.app_label)

    TEMPLATES_ENV = jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
        extensions=["jinja2.ext.i18n"])

    DEFAULT_TEMPLATE = "testjob_notification.txt"
    DEFAULT_IRC_TEMPLATE = "testjob_irc_notification.txt"
    DEFAULT_IRC_HANDLE = "lava-bot"

    QUERY_LIMIT = 5

    test_job = models.OneToOneField(
        TestJob,
        null=False,
        on_delete=models.CASCADE)

    REGRESSION = 0
    PROGRESSION = 1
    TYPE_CHOICES = (
        (REGRESSION, 'regression'),
        (PROGRESSION, 'progression'),
    )
    TYPE_MAP = {
        'regression': REGRESSION,
        'progression': PROGRESSION,
    }

    type = models.IntegerField(
        choices=TYPE_CHOICES,
        default=None,
        null=True,
        blank=True,
        verbose_name=_(u"Type"),
    )

    VERBOSE = 0
    QUIET = 1
    STATUS_ONLY = 2
    VERBOSITY_CHOICES = (
        (VERBOSE, 'verbose'),
        (QUIET, 'quiet'),
        (STATUS_ONLY, 'status-only'),
    )
    VERBOSITY_MAP = {
        'verbose': VERBOSE,
        'quiet': QUIET,
        'status-only': STATUS_ONLY,
    }

    verbosity = models.IntegerField(
        choices=VERBOSITY_CHOICES,
        default=QUIET,
    )

    template = models.CharField(
        max_length=50,
        default=None,
        null=True,
        blank=True,
        verbose_name='Template name'
    )

    callback_url = models.CharField(
        max_length=200,
        default=None,
        null=True,
        blank=True,
        verbose_name='Callback URL'
    )

    GET = 0
    POST = 1
    METHOD_CHOICES = (
        (GET, 'GET'),
        (POST, 'POST'),
    )
    METHOD_MAP = {
        'GET': GET,
        'POST': POST,
    }

    callback_method = models.IntegerField(
        choices=METHOD_CHOICES,
        default=None,
        null=True,
        blank=True,
        verbose_name=_(u"Callback method"),
    )

    callback_token = models.CharField(
        max_length=200,
        default=None,
        null=True,
        blank=True,
        verbose_name='Callback token'
    )

    MINIMAL = 0
    LOGS = 1
    RESULTS = 2
    ALL = 3
    DATASET_CHOICES = (
        (MINIMAL, 'minimal'),
        (LOGS, 'logs'),
        (RESULTS, 'results'),
        (ALL, 'all')
    )
    DATASET_MAP = {
        'minimal': MINIMAL,
        'logs': LOGS,
        'results': RESULTS,
        'all': ALL,
    }

    callback_dataset = models.IntegerField(
        choices=DATASET_CHOICES,
        default=None,
        null=True,
        blank=True,
        verbose_name=_(u"Callback dataset"),
    )

    URLENCODED = 0
    JSON = 1
    CONTENT_TYPE_CHOICES = (
        (URLENCODED, 'urlencoded'),
        (JSON, 'json')
    )
    CONTENT_TYPE_MAP = {
        'urlencoded': URLENCODED,
        'json': JSON
    }

    callback_content_type = models.IntegerField(
        choices=CONTENT_TYPE_CHOICES,
        default=None,
        null=True,
        blank=True,
        verbose_name=_(u"Callback content-type"),
    )

    blacklist = ArrayField(
        models.CharField(max_length=100, blank=True),
        null=True,
        blank=True
    )

    time_sent = models.DateTimeField(
        verbose_name=_(u"Time sent"),
        auto_now=False,
        auto_now_add=True,
        editable=False
    )

    query_owner = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name='Query owner'
    )

    query_name = models.CharField(
        max_length=1024,
        default=None,
        null=True,
        blank=True,
        verbose_name='Query name',
    )

    entity = models.ForeignKey(
        ContentType,
        null=True,
        blank=True
    )

    conditions = models.CharField(
        max_length=400,
        default=None,
        null=True,
        blank=True,
        verbose_name='Conditions'
    )

    def get_query_results(self):
        from lava_results_app.models import Query
        if self.query_name:
            query = Query.objects.get(name=self.query_name,
                                      owner=self.query_owner)
            # We use query_owner as user here since we show only status.
            return query.get_results(self.query_owner)[:self.QUERY_LIMIT]
        else:
            return Query.get_queryset(
                self.entity,
                Query.parse_conditions(self.entity, self.conditions),
                self.QUERY_LIMIT)

    def get_query_link(self):
        from lava_results_app.models import Query
        if self.query_name:
            query = Query.objects.get(name=self.query_name,
                                      owner=self.query_owner)
            return query.get_absolute_url()
        else:
            # Make absolute URL manually.
            return "%s?entity=%s&conditions=%s" % (
                reverse("lava.results.query_custom"),
                self.entity.model,
                self.conditions)

    def invoke_callback(self):
        logger = logging.getLogger('lava_scheduler_app')
        callback_data = self.get_callback_data()
        headers = {}

        if callback_data:
            headers['Authorization'] = callback_data['token']
            if self.callback_content_type == Notification.JSON:
                callback_data = simplejson.dumps(callback_data)
                headers['Content-Type'] = 'application/json'
            else:
                callback_data = urlencode(callback_data)
                headers['Content-Type'] = 'application/x-www-form-urlencoded'

        if self.callback_url:
            try:
                logger.info("Sending request to callback_url %s" % self.callback_url)
                request = Request(self.callback_url, callback_data, headers)
                urlopen(request)

            except Exception as ex:
                logger.warning("Problem sending request to %s: %s" % (
                    self.callback_url, ex))

    def get_callback_data(self):

        from lava_results_app.dbutils import export_testcase

        if self.callback_method == Notification.GET:
            return None
        else:

            data = {
                "id": self.test_job.pk,
                "state": self.test_job.state,
                "state_string": self.test_job.get_state_display(),
                "health": self.test_job.health,
                "health_string": self.test_job.get_health_display(),
                "submit_time": str(self.test_job.submit_time),
                "start_time": str(self.test_job.start_time),
                "end_time": str(self.test_job.end_time),
                "submitter_username": self.test_job.submitter.username,
                "is_pipeline": self.test_job.is_pipeline,
                "failure_comment": self.test_job.failure_comment,
                "priority": self.test_job.priority,
                "description": self.test_job.description,
                "actual_device_id": self.test_job.actual_device_id,
                "definition": self.test_job.definition,
                "metadata": self.test_job.get_metadata_dict(),
                "token": self.callback_token
            }

            # Logs.
            output_file = self.test_job.output_file()
            if output_file and self.callback_dataset in [Notification.LOGS,
                                                         Notification.ALL]:
                data["log"] = self.test_job.output_file().read().encode(
                    'UTF-8')

            # Results.
            if self.callback_dataset in [Notification.RESULTS,
                                         Notification.ALL]:
                data["results"] = {}
                for test_suite in self.test_job.testsuite_set.all():
                    yaml_list = []
                    for test_case in test_suite.testcase_set.all():
                        yaml_list.append(export_testcase(test_case))
                    data["results"][test_suite.name] = yaml.dump(yaml_list)

            return data


class NotificationRecipient(models.Model):

    class Meta:
        unique_together = ("user", "notification", "method")

    user = models.ForeignKey(
        User,
        default=None,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        verbose_name='Notification user recipient'
    )

    email = models.CharField(
        max_length=100,
        default=None,
        null=True,
        blank=True,
        verbose_name='recipient email'
    )

    irc_handle = models.CharField(
        max_length=40,
        default=None,
        null=True,
        blank=True,
        verbose_name='IRC handle'
    )

    irc_server = models.CharField(
        max_length=40,
        default=None,
        null=True,
        blank=True,
        verbose_name='IRC server'
    )

    notification = models.ForeignKey(
        Notification,
        null=False,
        on_delete=models.CASCADE,
        verbose_name='Notification'
    )

    SENT = 0
    NOT_SENT = 1
    STATUS_CHOICES = (
        (SENT, 'sent'),
        (NOT_SENT, 'not sent'),
    )
    STATUS_MAP = {
        'sent': SENT,
        'not sent': NOT_SENT,
    }

    status = models.IntegerField(
        choices=STATUS_CHOICES,
        default=NOT_SENT,
        verbose_name=_(u"Status"),
    )

    EMAIL = 0
    EMAIL_STR = 'email'
    IRC = 1
    IRC_STR = 'irc'

    METHOD_CHOICES = (
        (EMAIL, EMAIL_STR),
        (IRC, IRC_STR),
    )
    METHOD_MAP = {
        EMAIL_STR: EMAIL,
        IRC_STR: IRC,
    }

    method = models.IntegerField(
        choices=METHOD_CHOICES,
        default=EMAIL,
        verbose_name=_(u"Method"),
    )

    @property
    def email_address(self):
        if self.email:
            return self.email
        else:
            return self.user.email

    @property
    def irc_handle_name(self):
        if self.irc_handle:
            return self.irc_handle
        else:
            try:
                return self.user.extendeduser.irc_handle
            except:
                return None

    @property
    def irc_server_name(self):
        if self.irc_server:
            return self.irc_server
        else:
            try:
                return self.user.extendeduser.irc_server
            except:
                return None


@receiver(pre_save, sender=TestJob, dispatch_uid="process_notifications")
def process_notifications(sender, **kwargs):
    new_job = kwargs["instance"]
    notification_state = [TestJob.STATE_RUNNING, TestJob.STATE_FINISHED]
    # Send only for pipeline jobs.
    # If it's a new TestJob, no need to send notifications.
    if new_job.is_pipeline and new_job.id:
        old_job = TestJob.objects.get(pk=new_job.id)
        if new_job.state in notification_state and \
           old_job.state != new_job.state:
            job_def = yaml.load(new_job.definition)
            if "notify" in job_def:
                if new_job.notification_criteria(job_def["notify"]["criteria"],
                                                 old_job):
                    try:
                        old_job.notification
                    except ObjectDoesNotExist:
                        new_job.create_notification(job_def["notify"])

                    new_job.send_notifications()


class TestJobUser(models.Model):

    class Meta:
        unique_together = ("test_job", "user")
        permissions = (
            ('cancel_resubmit_testjob', 'Can cancel or resubmit test jobs'),
        )

    user = models.ForeignKey(
        User,
        null=False,
        on_delete=models.CASCADE)

    test_job = models.ForeignKey(
        TestJob,
        null=False,
        on_delete=models.CASCADE)

    is_favorite = models.BooleanField(
        default=False,
        verbose_name='Favorite job')

    def __str__(self):
        if self.user:
            return self.user.username
        return ''
