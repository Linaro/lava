# -*- coding: utf-8 -*-
# Copyright (C) 2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA.  If not, see <http://www.gnu.org/licenses/>.

# pylint: disable=too-many-lines

import contextlib
import datetime
import jinja2
import logging
import os
import uuid
import gzip
import simplejson
import yaml
from nose.tools import nottest
from django.db.models import Q
from django.conf import settings
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE
from django.contrib.postgres.fields import ArrayField
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.urls import reverse
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.utils.safestring import mark_safe

from django_restricted_resource.models import (
    RestrictedResource,
    RestrictedResourceManager,
)

from lava_common.exceptions import ConfigurationError
from lava_results_app.utils import export_testcase
from lava_scheduler_app import utils
from lava_scheduler_app.logutils import read_logs
from lava_scheduler_app.managers import RestrictedTestJobQuerySet
from lava_scheduler_app.schema import SubmissionException, validate_device

import requests

# pylint: disable=invalid-name,no-self-use,too-many-public-methods,too-few-public-methods
# pylint: disable=too-many-branches,too-many-return-statements,too-many-instance-attributes


class JSONDataError(ValueError):
    """Error raised when JSON is syntactically valid but ill-formed."""


class DevicesUnavailableException(UserWarning):
    """Error raised when required number of devices are unavailable."""


class ExtendedUser(models.Model):

    user = models.OneToOneField(User)

    irc_handle = models.CharField(
        max_length=40, default=None, null=True, blank=True, verbose_name="IRC handle"
    )

    irc_server = models.CharField(
        max_length=40, default=None, null=True, blank=True, verbose_name="IRC server"
    )

    def __str__(self):
        return "%s: %s@%s" % (self.user, self.irc_handle, self.irc_server)


class Tag(models.Model):

    name = models.SlugField(unique=True)

    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name.lower()


class Architecture(models.Model):
    name = models.CharField(
        primary_key=True,
        verbose_name="Architecture version",
        help_text="e.g. ARMv7",
        max_length=100,
        editable=True,
    )

    def __str__(self):
        return self.pk


class ProcessorFamily(models.Model):
    name = models.CharField(
        primary_key=True,
        verbose_name="Processor Family",
        help_text="e.g. OMAP4, Exynos",
        max_length=100,
        editable=True,
    )

    def __str__(self):
        return self.pk


class Alias(models.Model):
    class Meta:
        verbose_name_plural = "Aliases"

    name = models.CharField(
        primary_key=True,
        verbose_name="Alias for this device-type",
        help_text="e.g. the device tree name(s)",
        max_length=200,
        editable=True,
    )
    device_type = models.ForeignKey("DeviceType", related_name="aliases", null=True)

    def __str__(self):
        return self.pk

    def full_clean(self, exclude=None, validate_unique=True):
        if DeviceType.objects.filter(name=self.name).exists():
            raise ValidationError(
                "DeviceType with name '%s' already exists." % self.name
            )
        super().full_clean(exclude=exclude, validate_unique=validate_unique)


class BitWidth(models.Model):
    width = models.PositiveSmallIntegerField(
        primary_key=True,
        verbose_name="Processor bit width",
        help_text="integer: e.g. 32 or 64",
        editable=True,
    )

    def __str__(self):
        return "%d" % self.pk


class Core(models.Model):
    name = models.CharField(
        primary_key=True,
        verbose_name="CPU core",
        help_text="Name of a specific CPU core, e.g. Cortex-A9",
        editable=True,
        max_length=100,
    )

    def __str__(self):
        return self.pk


class DeviceType(models.Model):
    """
    A class of device, for example a pandaboard or a snowball.
    """

    name = models.SlugField(
        primary_key=True, editable=True
    )  # read-only after create via admin.py

    architecture = models.ForeignKey(
        Architecture,
        related_name="device_types",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )

    processor = models.ForeignKey(
        ProcessorFamily,
        related_name="device_types",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )

    cpu_model = models.CharField(
        verbose_name="CPU model",
        help_text="e.g. a list of CPU model descriptive strings: OMAP4430 / OMAP4460",
        max_length=100,
        blank=True,
        null=True,
        editable=True,
    )

    bits = models.ForeignKey(
        BitWidth,
        related_name="device_types",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )

    cores = models.ManyToManyField(Core, related_name="device_types", blank=True)

    core_count = models.PositiveSmallIntegerField(
        verbose_name="Total number of cores",
        help_text="Must be an equal number of each type(s) of core(s).",
        blank=True,
        null=True,
    )

    def __str__(self):
        return self.name

    def full_clean(self, exclude=None, validate_unique=True):
        if Alias.objects.filter(name=self.name).exists():
            raise ValidationError("Alias with name '%s' already exists." % self.name)
        super().full_clean(exclude=exclude, validate_unique=validate_unique)

    description = models.TextField(
        verbose_name=_("Device Type Description"),
        max_length=200,
        null=True,
        blank=True,
        default=None,
    )

    health_frequency = models.IntegerField(
        verbose_name="How often to run health checks", default=24
    )

    disable_health_check = models.BooleanField(
        default=False, verbose_name="Disable health check for devices of this type"
    )

    HEALTH_PER_HOUR = 0
    HEALTH_PER_JOB = 1
    HEALTH_DENOMINATOR = ((HEALTH_PER_HOUR, "hours"), (HEALTH_PER_JOB, "jobs"))

    health_denominator = models.IntegerField(
        choices=HEALTH_DENOMINATOR,
        default=HEALTH_PER_HOUR,
        verbose_name="Initiate health checks by hours or by jobs.",
        help_text=(
            "Choose to submit a health check every N hours "
            "or every N jobs. Balance against the duration of "
            "a health check job and the average job duration."
        ),
    )

    display = models.BooleanField(
        default=True,
        help_text=(
            "Should this be displayed in the GUI or not. This can be "
            "useful if you are removing all devices of this type but don't "
            "want to loose the test results generated by the devices."
        ),
    )

    owners_only = models.BooleanField(
        default=False,
        help_text="Hide this device type for all users except owners of "
        "devices of this type.",
    )

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
        devices = (
            Device.objects.filter(device_type=self)
            .only("user", "group")
            .select_related("user", "group")
        )
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

        devices = (
            Device.objects.filter(device_type=self)
            .only("state", "health", "user", "group")
            .select_related("user", "group")
        )

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
        verbose_name="Default owner of unrestricted devices", unique=True, default=False
    )

    def __str__(self):
        if self.user:
            return self.user.username
        return ""


class Worker(models.Model):
    """
    A worker node to which devices are attached.
    """

    hostname = models.CharField(
        verbose_name=_("Hostname"),
        max_length=200,
        primary_key=True,
        default=None,
        editable=True,
    )

    STATE_ONLINE, STATE_OFFLINE = range(2)
    STATE_CHOICES = ((STATE_ONLINE, "Online"), (STATE_OFFLINE, "Offline"))
    state = models.IntegerField(
        choices=STATE_CHOICES, default=STATE_OFFLINE, editable=False
    )

    HEALTH_ACTIVE, HEALTH_MAINTENANCE, HEALTH_RETIRED = range(3)
    HEALTH_CHOICES = (
        (HEALTH_ACTIVE, "Active"),
        (HEALTH_MAINTENANCE, "Maintenance"),
        (HEALTH_RETIRED, "Retired"),
    )
    health = models.IntegerField(choices=HEALTH_CHOICES, default=HEALTH_ACTIVE)

    description = models.TextField(
        verbose_name=_("Worker Description"),
        max_length=200,
        null=True,
        blank=True,
        default=None,
        editable=True,
    )

    last_ping = models.DateTimeField(verbose_name=_("Last ping"), default=timezone.now)

    def __str__(self):
        return self.hostname

    def can_admin(self, user):
        return user.has_perm("lava_scheduler_app.change_worker")

    def can_update(self, user):
        if user.has_perm("lava_scheduler_app.change_worker"):
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

    def retired_devices_count(self):
        return self.device_set.filter(health=Device.HEALTH_RETIRED).count()

    def go_health_active(self, user, reason=None):
        if reason:
            self.log_admin_entry(
                user, "%s → Active (%s)" % (self.get_health_display(), reason)
            )
        else:
            self.log_admin_entry(user, "%s → Active" % self.get_health_display())
        for device in self.device_set.all().select_for_update():
            device.worker_signal("go_health_active", user, self.state, self.health)
            device.save()
        self.health = Worker.HEALTH_ACTIVE

    def go_health_maintenance(self, user, reason=None):
        if reason:
            self.log_admin_entry(
                user, "%s → Maintenance (%s)" % (self.get_health_display(), reason)
            )
        else:
            self.log_admin_entry(user, "%s → Maintenance" % self.get_health_display())
        for device in self.device_set.all().select_for_update():
            device.worker_signal("go_health_maintenance", user, self.state, self.health)
            device.save()
        self.health = Worker.HEALTH_MAINTENANCE

    def go_health_retired(self, user, reason=None):
        if reason:
            self.log_admin_entry(
                user, "%s → Retired (%s)" % (self.get_health_display(), reason)
            )
        else:
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
            change_message=reason,
        )


class Device(RestrictedResource):
    """
    A device that we can run tests on.
    """

    CONFIG_PATH = "/etc/lava-server/dispatcher-config/devices"
    HEALTH_CHECK_PATH = "/etc/lava-server/dispatcher-config/health-checks"

    hostname = models.CharField(
        verbose_name=_("Hostname"),
        max_length=200,
        primary_key=True,
        editable=True,  # read-only after create via admin.py
    )

    device_type = models.ForeignKey(DeviceType, verbose_name=_("Device type"))

    device_version = models.CharField(
        verbose_name=_("Device Version"),
        max_length=200,
        null=True,
        default=None,
        blank=True,
    )

    physical_owner = models.ForeignKey(
        User,
        related_name="physicalowner",
        null=True,
        blank=True,
        default=None,
        verbose_name=_("User with physical access"),
        on_delete=models.SET_NULL,
    )

    physical_group = models.ForeignKey(
        Group,
        related_name="physicalgroup",
        null=True,
        blank=True,
        default=None,
        verbose_name=_("Group with physical access"),
    )

    description = models.TextField(
        verbose_name=_("Device Description"),
        max_length=200,
        null=True,
        blank=True,
        default=None,
    )

    tags = models.ManyToManyField(Tag, blank=True)

    # This state is a cache computed from the device health and jobs. So keep
    # it read only to the admins
    STATE_IDLE, STATE_RESERVED, STATE_RUNNING = range(3)
    STATE_CHOICES = (
        (STATE_IDLE, "Idle"),
        (STATE_RESERVED, "Reserved"),
        (STATE_RUNNING, "Running"),
    )
    state = models.IntegerField(
        choices=STATE_CHOICES, default=STATE_IDLE, editable=False
    )

    # The device health helps to decide what to do next with the device
    HEALTH_GOOD, HEALTH_UNKNOWN, HEALTH_LOOPING, HEALTH_BAD, HEALTH_MAINTENANCE, HEALTH_RETIRED = range(
        6
    )
    HEALTH_CHOICES = (
        (HEALTH_GOOD, "Good"),
        (HEALTH_UNKNOWN, "Unknown"),
        (HEALTH_LOOPING, "Looping"),
        (HEALTH_BAD, "Bad"),
        (HEALTH_MAINTENANCE, "Maintenance"),
        (HEALTH_RETIRED, "Retired"),
    )
    HEALTH_REVERSE = {
        "GOOD": HEALTH_GOOD,
        "UNKNOWN": HEALTH_UNKNOWN,
        "LOOPING": HEALTH_LOOPING,
        "BAD": HEALTH_BAD,
        "MAINTENANCE": HEALTH_MAINTENANCE,
        "RETIRED": HEALTH_RETIRED,
    }
    health = models.IntegerField(choices=HEALTH_CHOICES, default=HEALTH_MAINTENANCE)

    last_health_report_job = models.OneToOneField(
        "TestJob",
        blank=True,
        unique=True,
        null=True,
        related_name="+",
        on_delete=models.SET_NULL,
    )

    # TODO: make this mandatory
    worker_host = models.ForeignKey(
        Worker,
        verbose_name=_("Worker Host"),
        null=True,
        blank=True,
        default=None,
        on_delete=models.SET_NULL,
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
        if not default_user_list:
            superusers = User.objects.filter(is_superuser=True).order_by("id")[:1]
            if superusers:
                first_super_user = superusers[0]
                if self.group is None:
                    self.user = User.objects.filter(username=first_super_user.username)[
                        0
                    ]
                default_owner = DefaultDeviceOwner()
                default_owner.user = User.objects.filter(
                    username=first_super_user.username
                )[0]
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
                "Cannot be owned by a user and a group at the same time"
            )

    def __str__(self):
        return "%s (%s, health %s)" % (
            self.hostname,
            self.get_state_display(),
            self.get_health_display(),
        )

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
        if user.has_perm("lava_scheduler_app.change_device"):
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
        try:
            rendered = self.load_configuration()
            validate_device(rendered)
        except (SubmissionException, yaml.YAMLError):
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
            change_message=reason,
        )

    def testjob_signal(self, signal, job, infrastructure_error=False):

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

            prev_health_display = self.get_health_display()
            if job.health_check:
                self.last_health_report_job = job
                if self.health == Device.HEALTH_LOOPING:
                    if job.health == TestJob.HEALTH_INCOMPLETE:
                        # Looping is persistent until cancelled by the admin.
                        self.log_admin_entry(
                            None,
                            "%s → %s (Looping health-check [%s] failed)"
                            % (prev_health_display, self.get_health_display(), job.id),
                        )
                elif self.health in [
                    Device.HEALTH_GOOD,
                    Device.HEALTH_UNKNOWN,
                    Device.HEALTH_BAD,
                ]:
                    if job.health == TestJob.HEALTH_COMPLETE:
                        self.health = Device.HEALTH_GOOD
                        msg = "completed"
                    elif job.health == TestJob.HEALTH_INCOMPLETE:
                        self.health = Device.HEALTH_BAD
                        msg = "failed"
                    elif job.health == TestJob.HEALTH_CANCELED:
                        self.health = Device.HEALTH_BAD
                        msg = "canceled"
                    else:
                        raise NotImplementedError("Unexpected TestJob health")
                    self.log_admin_entry(
                        None,
                        "%s → %s (health-check [%s] %s)"
                        % (prev_health_display, self.get_health_display(), job.id, msg),
                    )
            elif infrastructure_error:
                self.health = Device.HEALTH_UNKNOWN
                self.log_admin_entry(
                    None,
                    "%s → %s (Infrastructure error after %s)"
                    % (prev_health_display, self.get_health_display(), job.display_id),
                )

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
            self.log_admin_entry(
                user, "%s → Unknown (worker going active)" % self.get_health_display()
            )
            self.health = Device.HEALTH_UNKNOWN

        elif signal == "go_health_maintenance":
            if self.health in [
                Device.HEALTH_BAD,
                Device.HEALTH_MAINTENANCE,
                Device.HEALTH_RETIRED,
            ]:
                return
            self.log_admin_entry(
                user,
                "%s → Maintenance (worker going maintenance)"
                % self.get_health_display(),
            )
            self.health = Device.HEALTH_MAINTENANCE

        elif signal == "go_health_retired":
            if self.health in [Device.HEALTH_BAD, Device.HEALTH_RETIRED]:
                return
            self.log_admin_entry(
                user, "%s → Retired (worker going retired)" % self.get_health_display()
            )
            self.health = Device.HEALTH_RETIRED

        else:
            raise NotImplementedError("Unknown signal %s" % signal)

    def load_configuration(self, job_ctx=None, output_format="dict"):
        """
        Maps the device dictionary to the static templates in /etc/.
        raise: this function can raise OSError, jinja2.TemplateError or yaml.YAMLError -
            handling these exceptions may be context-dependent, users will need
            useful messages based on these exceptions.
        """
        # The job_ctx should not be None while an empty dict is ok
        if job_ctx is None:
            job_ctx = {}

        if output_format == "raw":
            try:
                with open(
                    os.path.join(Device.CONFIG_PATH, "%s.jinja2" % self.hostname), "r"
                ) as f_in:
                    return f_in.read()
            except OSError:
                return None

        # Create the environment
        env = jinja2.Environment(  # nosec - YAML, not HTML, no XSS scope.
            autoescape=False,
            loader=jinja2.FileSystemLoader(
                [
                    Device.CONFIG_PATH,
                    os.path.join(os.path.dirname(Device.CONFIG_PATH), "device-types"),
                ]
            ),
            trim_blocks=True,
        )

        try:
            template = env.get_template("%s.jinja2" % self.hostname)
            device_template = template.render(**job_ctx)
        except jinja2.TemplateError:
            return None

        if output_format == "yaml":
            return device_template
        else:
            return yaml.safe_load(device_template)

    def minimise_configuration(self, data):
        """
        Support for dynamic connections which only require
        critical elements of device configuration.
        Principally drop top level parameters and commands
        like power.
        """
        data["constants"]["kernel-start-message"] = ""
        device_configuration = {
            "hostname": self.hostname,
            "constants": data["constants"],
            "timeouts": data["timeouts"],
            "actions": {
                "deploy": {
                    "connections": data["actions"]["deploy"]["connections"],
                    "methods": data["actions"]["deploy"]["methods"],
                },
                "boot": {
                    "connections": data["actions"]["boot"]["connections"],
                    "methods": data["actions"]["boot"]["methods"],
                },
            },
        }
        return device_configuration

    def save_configuration(self, data):
        try:
            with open(
                os.path.join(self.CONFIG_PATH, "%s.jinja2" % self.hostname), "w"
            ) as f_out:
                f_out.write(data)
            return True
        except OSError as exc:
            logger = logging.getLogger("lava_scheduler_app")
            logger.error(
                "Error saving device configuration for %s: %s", self.hostname, str(exc)
            )
            return False

    def get_extends(self):
        jinja_config = self.load_configuration(output_format="raw")
        if not jinja_config:
            return None

        env = jinja2.Environment(  # nosec - YAML, not HTML, no XSS scope.
            autoescape=False
        )
        try:
            ast = env.parse(jinja_config)
            extends = list(ast.find_all(jinja2.nodes.Extends))
            if len(extends) != 1:
                logger = logging.getLogger("lava_scheduler_app")
                logger.error("Found %d extends for %s", len(extends), self.hostname)
                return None
            else:
                return os.path.splitext(extends[0].template.value)[0]
        except jinja2.TemplateError as exc:
            logger = logging.getLogger("lava_scheduler_app")
            logger.error("Invalid template for %s: %s", self.hostname, str(exc))
            return None

    def get_health_check(self):
        # Get the device dictionary
        extends = self.get_extends()
        if not extends:
            return None

        filename = os.path.join(Device.HEALTH_CHECK_PATH, "%s.yaml" % extends)
        # Try if health check file is having a .yml extension
        if not os.path.exists(filename):
            filename = os.path.join(Device.HEALTH_CHECK_PATH, "%s.yml" % extends)
        try:
            with open(filename, "r") as f_in:
                return f_in.read()
        except OSError:
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


def _get_tag_list(tags):
    """
    Creates a list of Tag objects for the specified device tags
    for singlenode and multinode jobs.
    :param tags: a list of strings from the JSON
    :return: a list of tags which match the strings
    :raise: yaml.YAMLError if a tag cannot be found in the database.
    """
    taglist = []
    if not isinstance(tags, list):
        msg = "'device_tags' needs to be a list - received %s" % type(tags)
        raise yaml.YAMLError(msg)
    for tag_name in tags:
        try:
            taglist.append(Tag.objects.get(name=tag_name))
        except Tag.DoesNotExist:
            msg = "Device tag '%s' does not exist in the database." % tag_name
            raise yaml.YAMLError(msg)

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
    if not taglist:
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
    if not matched_devices and device_type:
        raise DevicesUnavailableException(
            "No devices of type %s are available which have all of the tags '%s'."
            % (device_type, ", ".join([x.name for x in taglist]))
        )
    if not matched_devices and hostname:
        raise DevicesUnavailableException(
            "Device %s does not support all of the tags '%s'."
            % (hostname, ", ".join([x.name for x in taglist]))
        )
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
    if not isinstance(list(device_list), list) or not device_list:
        # logic error
        return allow
    device_type = None
    for device in device_list:
        device_type = device.device_type
        if device.health != Device.HEALTH_RETIRED and device.can_submit(user):
            allow.append(device)
    if not allow:
        raise DevicesUnavailableException(
            "No devices of type %s are currently available to user %s"
            % (device_type, user)
        )
    return allow


def _check_tags_support(tag_devices, device_list, count=1):
    """
    Combines the Device Ownership list with the requested tag list and
    returns any devices which meet both criteria.
    If neither the job nor the device have any tags, tag_devices will
    be empty, so the check will pass.
    This function is called to check availability when a test job is submitted;
    it is called for both single node and multinode jobs.
    :param tag_devices: A list of devices which meet the tag
    requirements
    :param device_list: A list of devices to which the user is able
    to submit a TestJob
    :param count: Count of devices in the role to check for tag support, prior
    to scheduling.
    :raise: DevicesUnavailableException if there is no overlap between
    the two sets.
    """
    if not tag_devices:
        # no tags requested in the job: proceed.
        return
    if len(set(tag_devices) & set(device_list)) < count:
        raise DevicesUnavailableException(
            "Not enough devices available matching the requested tags."
        )


def _get_device_type(user, name):
    """
    Gets the device type for the supplied name and ensures
    the user is an owner of at least one of those devices.
    :param user: the user submitting the TestJob
    """
    logger = logging.getLogger("lava_scheduler_app")
    # try to find matching alias first
    try:
        alias = Alias.objects.get(name=name)
        device_type = alias.device_type
    except Alias.DoesNotExist:
        try:
            device_type = DeviceType.objects.get(name=name)
        except DeviceType.DoesNotExist:
            msg = "Device type '%s' is unavailable." % name
            logger.error(msg)
            raise DevicesUnavailableException(msg)

    if not device_type.some_devices_visible_to(user):
        msg = "Device type '%s' is unavailable to user '%s'" % (name, user.username)
        logger.error(msg)
        raise DevicesUnavailableException(msg)
    return device_type


# pylint: disable=too-many-arguments,too-many-locals
def _create_pipeline_job(
    job_data,
    user,
    taglist,
    device=None,
    device_type=None,
    target_group=None,
    orig=None,
    health_check=False,
):

    if not isinstance(job_data, dict):
        # programming error
        raise RuntimeError("Invalid job data %s" % job_data)

    if "connection" in job_data:
        device_type = None
    elif not device and not device_type:
        # programming error
        return None

    if not taglist:
        taglist = []

    # Handle priority
    priority = TestJob.MEDIUM
    if "priority" in job_data:
        key = job_data["priority"]
        if isinstance(key, int):
            priority = int(key)
            if priority < TestJob.LOW or priority > TestJob.HIGH:
                raise SubmissionException(
                    "Invalid job priority: %s. "
                    "Should be in [%d, %d]" % (key, TestJob.LOW, TestJob.HIGH)
                )
        else:
            priority = {j.upper(): i for i, j in TestJob.PRIORITY_CHOICES}.get(
                key.upper()
            )
            if priority is None:
                raise SubmissionException("Invalid job priority: %r" % key)

    public_state = True
    visibility = TestJob.VISIBLE_PUBLIC
    viewing_groups = []
    param = job_data["visibility"]

    if health_check and device.device_type.owners_only:
        # 'lava-health' user is normally allowed to "ignore" visibility
        if isinstance(param, str):
            if param == "public":
                raise ConfigurationError(
                    "Publicly visible health check requested for a hidden device-type."
                )

    if isinstance(param, str):
        if param == "personal":
            public_state = False
            visibility = TestJob.VISIBLE_PERSONAL
    elif isinstance(param, dict):
        public_state = False
        if "group" in param:
            visibility = TestJob.VISIBLE_GROUP
            known_groups = list(Group.objects.filter(name__in=param["group"]))
            if not known_groups:
                raise SubmissionException(
                    "No known groups were found in the visibility list."
                )
            viewing_groups.extend(known_groups)

    if not orig:
        orig = yaml.safe_dump(job_data)
    job = TestJob(
        definition=yaml.safe_dump(job_data),
        original_definition=orig,
        submitter=user,
        requested_device_type=device_type,
        target_group=target_group,
        description=job_data["job_name"],
        health_check=health_check,
        user=user,
        is_public=public_state,
        visibility=visibility,
        priority=priority,
    )
    job.save()

    # need a valid job (witha  primary_key )before tags and groups can be
    # assigned
    job.tags.add(*taglist)
    job.viewing_groups.add(*viewing_groups)

    return job


def _pipeline_protocols(
    job_data, user, yaml_data=None
):  # pylint: disable=too-many-locals,too-many-branches
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

    Actual device assignment happens in lava-master.

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
    if isinstance(job_data, dict) and "protocols" not in job_data:
        return device_list

    if not yaml_data:
        yaml_data = yaml.safe_dump(job_data)
    role_dictionary = {}  # map of the multinode group
    if "lava-multinode" in job_data["protocols"]:
        # create target_group uuid, just a label for the coordinator.
        target_group = str(uuid.uuid4())

        # Handle the requirements of the Multinode protocol
        # FIXME: needs a schema check
        # FIXME: the vland protocol will affect the device_list
        if "roles" in job_data["protocols"]["lava-multinode"]:
            for role in job_data["protocols"]["lava-multinode"]["roles"]:
                role_dictionary[role] = {"devices": [], "tags": []}
                params = job_data["protocols"]["lava-multinode"]["roles"][role]
                if "device_type" in params and "connection" in params:
                    raise SubmissionException(
                        "lava-multinode protocol cannot support device_type and connection for a single role."
                    )
                if "device_type" not in params and "connection" in params:
                    # always allow support for dynamic connections which have no devices.
                    if "host_role" not in params:
                        raise SubmissionException(
                            "connection specified without a host_role"
                        )
                    continue
                device_type = _get_device_type(user, params["device_type"])
                role_dictionary[role]["device_type"] = device_type

                allowed_devices = []
                device_list = Device.objects.filter(
                    Q(device_type=device_type), ~Q(health=Device.HEALTH_RETIRED)
                )
                allowed_devices.extend(_check_submit_to_device(list(device_list), user))

                if len(allowed_devices) < params["count"]:
                    raise DevicesUnavailableException(
                        "Not enough devices of type %s are currently "
                        "available to user %s" % (device_type, user)
                    )
                role_dictionary[role]["tags"] = _get_tag_list(params.get("tags", []))
                if role_dictionary[role]["tags"]:
                    supported = _check_tags(
                        role_dictionary[role]["tags"], device_type=device_type
                    )
                    _check_tags_support(supported, allowed_devices, params["count"])

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
        parent = (
            None
        )  # track the zero id job as the parent of the group in the sub_id text field
        for role, role_dict in role_dictionary.items():
            for node_data in job_dictionary[role]:
                job = _create_pipeline_job(
                    node_data,
                    user,
                    target_group=target_group,
                    taglist=role_dict["tags"],
                    device_type=role_dict.get("device_type"),
                    orig=None,  # store the dump of the split yaml as the job definition
                )
                if not job:
                    raise SubmissionException("Unable to create job for %s" % node_data)
                if not parent:
                    parent = job.id
                job.sub_id = "%d.%d" % (
                    parent,
                    node_data["protocols"]["lava-multinode"]["sub_id"],
                )
                job.multinode_definition = (
                    yaml_data
                )  # store complete submission, inc. comments
                job.save()
                job_object_list.append(job)

        return job_object_list


@nottest
class TestJob(RestrictedResource):
    """
    A test job is a test process that will be run on a Device.
    """

    class Meta:
        index_together = ["health", "state", "requested_device_type"]

    objects = RestrictedResourceManager.from_queryset(RestrictedTestJobQuerySet)()

    # VISIBILITY levels are subject to any device restrictions and hidden device type rules
    VISIBLE_PUBLIC = 0  # anyone can view, submit or resubmit
    VISIBLE_PERSONAL = 1  # only the submitter can view, submit or resubmit
    VISIBLE_GROUP = (
        2
    )  # A single group is specified, all users in that group (and that group only) can view.

    VISIBLE_CHOICES = (
        (
            VISIBLE_PUBLIC,
            "Publicly visible",
        ),  # publicly and publically are equivalent meaning
        (VISIBLE_PERSONAL, "Personal only"),
        (VISIBLE_GROUP, "Group only"),
    )

    NOTIFY_EMAIL_METHOD = "email"
    NOTIFY_IRC_METHOD = "irc"

    id = models.AutoField(primary_key=True)

    sub_id = models.CharField(verbose_name=_("Sub ID"), blank=True, max_length=200)

    target_group = models.CharField(
        verbose_name=_("Target Group"),
        blank=True,
        max_length=64,
        null=True,
        default=None,
    )

    submitter = models.ForeignKey(User, verbose_name=_("Submitter"), related_name="+")

    visibility = models.IntegerField(
        verbose_name=_("Visibility type"),
        help_text=_(
            "Visibility affects the TestJob and all results arising from that job, "
            "including Queries and Reports."
        ),
        choices=VISIBLE_CHOICES,
        default=VISIBLE_PUBLIC,
        editable=True,
    )

    viewing_groups = models.ManyToManyField(
        # functionally, may be restricted to only one group at a time
        # depending on implementation complexity
        Group,
        verbose_name=_("Viewing groups"),
        help_text=_(
            "Adding groups to an intersection of groups reduces visibility."
            "Adding groups to a union of groups expands visibility."
        ),
        related_name="viewing_groups",
        blank=True,
        default=None,
        editable=True,
    )

    description = models.CharField(
        verbose_name=_("Description"),
        max_length=200,
        null=True,
        blank=True,
        default=None,
    )

    health_check = models.BooleanField(default=False)

    # Only one of requested_device_type or dynamic_connection should be
    # non-null. Dynamic connections have no device.
    requested_device_type = models.ForeignKey(
        DeviceType, null=True, default=None, related_name="+", blank=True
    )

    @property
    def dynamic_connection(self):
        """
        Secondary connection detection - multinode only.
        A Primary connection needs a real device (persistence).
        """
        if not self.is_multinode or not self.definition:
            return False
        job_data = yaml.safe_load(self.definition)
        return "connection" in job_data

    tags = models.ManyToManyField(Tag, blank=True)

    # This is set once the job starts or is reserved.
    actual_device = models.ForeignKey(
        Device, null=True, default=None, related_name="testjobs", blank=True
    )

    submit_time = models.DateTimeField(
        verbose_name=_("Submit time"), auto_now=False, auto_now_add=True, db_index=True
    )
    start_time = models.DateTimeField(
        verbose_name=_("Start time"),
        auto_now=False,
        auto_now_add=False,
        null=True,
        blank=True,
        editable=False,
    )
    end_time = models.DateTimeField(
        verbose_name=_("End time"),
        auto_now=False,
        auto_now_add=False,
        null=True,
        blank=True,
        editable=False,
    )

    @property
    def duration(self):
        if self.end_time is None or self.start_time is None:
            return None
        # Only return seconds and not milliseconds
        return datetime.timedelta(seconds=(self.end_time - self.start_time).seconds)

    STATE_SUBMITTED, STATE_SCHEDULING, STATE_SCHEDULED, STATE_RUNNING, STATE_CANCELING, STATE_FINISHED = range(
        6
    )
    STATE_CHOICES = (
        (STATE_SUBMITTED, "Submitted"),
        (STATE_SCHEDULING, "Scheduling"),
        (STATE_SCHEDULED, "Scheduled"),
        (STATE_RUNNING, "Running"),
        (STATE_CANCELING, "Canceling"),
        (STATE_FINISHED, "Finished"),
    )
    STATE_REVERSE = {
        "Submitted": STATE_SUBMITTED,
        "Scheduling": STATE_SCHEDULING,
        "Scheduled": STATE_SCHEDULED,
        "Running": STATE_RUNNING,
        "Canceling": STATE_CANCELING,
        "Finished": STATE_FINISHED,
    }
    state = models.IntegerField(
        choices=STATE_CHOICES, default=STATE_SUBMITTED, editable=False
    )

    HEALTH_UNKNOWN, HEALTH_COMPLETE, HEALTH_INCOMPLETE, HEALTH_CANCELED = range(4)
    HEALTH_CHOICES = (
        (HEALTH_UNKNOWN, "Unknown"),
        (HEALTH_COMPLETE, "Complete"),
        (HEALTH_INCOMPLETE, "Incomplete"),
        (HEALTH_CANCELED, "Canceled"),
    )
    HEALTH_REVERSE = {
        "Unknown": HEALTH_UNKNOWN,
        "Complete": HEALTH_COMPLETE,
        "Incomplete": HEALTH_INCOMPLETE,
        "Canceled": HEALTH_CANCELED,
    }
    health = models.IntegerField(choices=HEALTH_CHOICES, default=HEALTH_UNKNOWN)

    def go_state_scheduling(self, device):
        """
        Used for multinode jobs when all jobs are not scheduled yet.
        When each sub jobs are scheduled, the state is change to
        STATE_SCHEDULED
        Jobs that are not multinode will directly use STATE_SCHEDULED
        """
        if device.state != Device.STATE_IDLE:
            raise Exception(
                "device is not IDLE: %s" % Device.STATE_CHOICES[device.state]
            )
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
                raise Exception(
                    "device is not IDLE: %s" % Device.STATE_CHOICES[device.state]
                )
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

    def go_state_finished(self, health, infrastructure_error=False):
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
            self.actual_device.testjob_signal(
                "go_state_finished", self, infrastructure_error
            )
            self.actual_device.save()

        # For multinode, cancel all sub jobs if the current job is essential
        # and it was a failure.
        if health == TestJob.HEALTH_INCOMPLETE and self.essential_role:
            for sub_job in self.sub_jobs_list:
                if sub_job != self:
                    sub_job.go_state_canceling(sub_cancel=True)
                    sub_job.save()

    def get_legacy_status(self):
        if self.state in [
            TestJob.STATE_SUBMITTED,
            TestJob.STATE_SCHEDULING,
            TestJob.STATE_SCHEDULED,
        ]:
            return 0
        elif self.state == TestJob.STATE_RUNNING:
            return 1
        elif self.state == TestJob.STATE_CANCELING:
            return 5
        elif self.health == TestJob.HEALTH_COMPLETE:
            return 2
        elif self.health in [TestJob.HEALTH_UNKNOWN, TestJob.HEALTH_INCOMPLETE]:
            return 3
        else:
            return 4

    def get_legacy_status_display(self):
        if self.state in [
            TestJob.STATE_SUBMITTED,
            TestJob.STATE_SCHEDULING,
            TestJob.STATE_SCHEDULED,
        ]:
            return "Submitted"
        elif self.state == TestJob.STATE_RUNNING:
            return "Running"
        elif self.state == TestJob.STATE_CANCELING:
            return "Canceling"
        elif self.health == TestJob.HEALTH_COMPLETE:
            return "Complete"
        elif self.health in [TestJob.HEALTH_UNKNOWN, TestJob.HEALTH_INCOMPLETE]:
            return "Incomplete"
        else:
            return "Canceled"

    LOW, MEDIUM, HIGH = (0, 50, 100)
    PRIORITY_CHOICES = ((LOW, "Low"), (MEDIUM, "Medium"), (HIGH, "High"))
    priority = models.IntegerField(
        choices=PRIORITY_CHOICES, default=MEDIUM, verbose_name=_("Priority")
    )

    definition = models.TextField(editable=False)

    original_definition = models.TextField(editable=False, blank=True)

    multinode_definition = models.TextField(editable=False, blank=True)

    # calculated by the master validation process.
    pipeline_compatibility = models.IntegerField(default=0, editable=False)

    @property
    def size_limit(self):
        return settings.LOG_SIZE_LIMIT * 1024 * 1024

    @property
    def output_dir(self):
        # Fallback to the old path if it does exist
        old_path = os.path.join(settings.MEDIA_ROOT, "job-output", "job-%s" % self.id)
        if os.path.exists(old_path):
            return old_path
        return os.path.join(
            settings.MEDIA_ROOT,
            "job-output",
            "%02d" % self.submit_time.year,
            "%02d" % self.submit_time.month,
            "%02d" % self.submit_time.day,
            str(self.id),
        )

    failure_tags = models.ManyToManyField(
        JobFailureTag, blank=True, related_name="failure_tags"
    )
    failure_comment = models.TextField(null=True, blank=True)

    @property
    def results_link(self):
        return reverse("lava.results.testjob", args=[self.id])

    @property
    def essential_role(self):  # pylint: disable=too-many-return-statements
        if not self.is_multinode:
            return False
        data = yaml.safe_load(self.definition)
        # would be nice to use reduce here but raising and catching TypeError is slower
        # than checking 'if .. in ' - most jobs will return False.
        if "protocols" not in data:
            return False
        if "lava-multinode" not in data["protocols"]:
            return False
        if "role" not in data["protocols"]["lava-multinode"]:
            return False
        if "essential" not in data["protocols"]["lava-multinode"]:
            return False
        return data["protocols"]["lava-multinode"]["essential"]

    @property
    def device_role(self):  # pylint: disable=too-many-return-statements
        if not self.is_multinode:
            return "Error"
        try:
            # For some old definition (when migrating from python2 to python3)
            # includes "!!python/unicode" statements that are not accepted by
            # yaml.safe_load().
            data = yaml.safe_load(self.definition)
        except yaml.YAMLError:
            return "Error"
        if "protocols" not in data:
            return "Error"
        if "lava-multinode" not in data["protocols"]:
            return "Error"
        if "role" not in data["protocols"]["lava-multinode"]:
            return "Error"
        return data["protocols"]["lava-multinode"]["role"]

    def __str__(self):
        job_type = "health_check" if self.health_check else "test"
        r = "%s (%s) %s job" % (
            self.get_state_display(),
            self.get_health_display(),
            job_type,
        )
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
        Runs the submission checks on incoming jobs.
        Either rejects the job with a DevicesUnavailableException (which the caller is expected to handle), or
        creates a TestJob object for the submission and saves that testjob into the database.
        This function must *never* be involved in setting the state of this job or the state of any associated device.
        Retains yaml_data as the original definition to retain comments.

        :return: a single TestJob object or a list
        (explicitly, a list, not a QuerySet) of evaluated TestJob objects
        """
        job_data = yaml.safe_load(yaml_data)

        # visibility checks
        if "visibility" not in job_data:
            raise SubmissionException("Job visibility must be specified.")
            # handle view and admin users and groups

        # pipeline protocol handling, e.g. lava-multinode
        job_list = _pipeline_protocols(job_data, user, yaml_data)
        if job_list:
            # explicitly a list, not a QuerySet.
            return job_list
        # singlenode only
        device_type = _get_device_type(user, job_data["device_type"])
        allow = _check_submit_to_device(
            list(Device.objects.filter(device_type=device_type)), user
        )
        if not allow:
            raise DevicesUnavailableException(
                "No devices of type %s are available." % device_type
            )
        taglist = _get_tag_list(job_data.get("tags", []))
        if taglist:
            supported = _check_tags(taglist, device_type=device_type)
            _check_tags_support(supported, allow)
        if original_job:
            # Add old job absolute url to metadata
            job_url = str(original_job.get_absolute_url())
            with contextlib.suppress(Site.DoesNotExist, ImproperlyConfigured):
                site = Site.objects.get_current()
                job_url = "http://%s%s" % (site.domain, job_url)

            job_data.setdefault("metadata", {}).setdefault("job.original", job_url)

        return _create_pipeline_job(
            job_data,
            user,
            taglist,
            device=None,
            device_type=device_type,
            orig=yaml_data,
        )

    def clean(self):
        """
        Implement the schema constraints for visibility for jobs so that
        admins cannot set a job into a logically inconsistent state.
        """
        # public settings must match
        if self.is_public and self.visibility != TestJob.VISIBLE_PUBLIC:
            raise ValidationError("is_public is set but visibility is not public.")
        elif not self.is_public and self.visibility == TestJob.VISIBLE_PUBLIC:
            raise ValidationError("is_public is not set but visibility is public.")
        return super().clean()

    def can_view(self, user):
        """
        Take over the checks behind RestrictedIDLinkColumn, for
        jobs which support a view user list or view group.
        For speed, the lookups on the user/group tables are only by id
        Any elements which would need admin access must be checked
        separately using can_admin instead.
        :param user:  the user making the request
        :return: True or False
        """
        if self._can_admin(user, resubmit=False):
            return True
        device_type = self.requested_device_type
        if device_type and device_type.owners_only:
            if not device_type.some_devices_visible_to(user):
                return False
        if self.is_public:
            return True
        logger = logging.getLogger("lava_scheduler_app")
        if self.visibility == self.VISIBLE_PUBLIC:
            # logical error
            logger.exception(
                "job [%s] visibility is public but job is not public.", self.id
            )
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
            perm = (
                user.is_superuser
                or user == self.submitter
                or owner
                or user.has_perm("lava_scheduler_app.cancel_resubmit_testjob")
            )
        return perm

    def can_change_priority(self, user):
        """
        Permission and state required to change job priority.
        Multinode jobs cannot have their priority changed.
        """
        return (
            user.is_superuser
            or user == self.submitter
            or user.has_perm("lava_scheduler_app.cancel_resubmit_testjob")
        )

    def can_annotate(self, user):
        """
        Permission required for user to add failure information to a job
        """
        return self._can_admin(user) and self.state == TestJob.STATE_FINISHED

    def can_cancel(self, user):
        states = [
            TestJob.STATE_SUBMITTED,
            TestJob.STATE_SCHEDULING,
            TestJob.STATE_SCHEDULED,
            TestJob.STATE_RUNNING,
        ]
        return self._can_admin(user) and self.state in states

    def can_resubmit(self, user):
        return user.is_superuser or user.has_perm(
            "lava_scheduler_app.cancel_resubmit_testjob"
        )

    def create_job_data(self, token=None, output=False, results=False):
        """
        Populates a dictionary used by the NotificationCallback
        and by the REST API, containing data about the test job.
        If output is True, the entire test job log file is included.
        If results is True, an export of all test cases is included.
        """
        data = {
            "id": self.pk,
            "status": self.get_legacy_status(),
            "status_string": self.get_legacy_status_display().lower(),
            "state": self.state,
            "state_string": self.get_state_display(),
            "health": self.health,
            "health_string": self.get_health_display(),
            "submit_time": str(self.submit_time),
            "start_time": str(self.start_time),
            "end_time": str(self.end_time),
            "submitter_username": self.submitter.username,
            "failure_comment": self.failure_comment,
            "priority": self.priority,
            "description": self.description,
            "actual_device_id": self.actual_device_id,
            "definition": self.definition,
            "metadata": self.get_metadata_dict(),
        }

        # Only add the token if it's not empty
        if token is not None:
            data["token"] = token

        # Logs.
        with contextlib.suppress(OSError):
            data["log"] = read_logs(self.output_dir)

        # Results.
        if results:
            data["results"] = {}
            for test_suite in self.testsuite_set.all():
                yaml_list = []
                for test_case in test_suite.testcase_set.all():
                    yaml_list.append(export_testcase(test_case))
                data["results"][test_suite.name] = yaml.dump(yaml_list)

        return data

    def set_failure_comment(self, message):
        if not self.failure_comment:
            self.failure_comment = message
        elif message not in self.failure_comment:
            self.failure_comment += message
        else:
            return
        self.save(update_fields=["failure_comment"])

    @property
    def sub_jobs_list(self):
        if self.is_multinode:
            jobs = TestJob.objects.filter(target_group=self.target_group).order_by("id")
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
            data = yaml.safe_load(self.definition)
        except yaml.YAMLError:
            return None
        if "host_role" not in data:
            return None
        parent = None
        # the protocol requires a count of 1 for any role specified as a host_role
        for worker_job in self.sub_jobs_list:
            if worker_job.device_role == data["host_role"]:
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
        if "." in str(job_id):
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
        # Get pass fail results per lava_scheduler_app.testjob.
        results = {}
        for suite in self.testsuite_set.all():
            results.update(suite.get_passfail_results())
        return results

    def get_measurement_results(self):
        # Get measurement values per lava_scheduler_app.testjob.
        # TODO: add min, max
        results = {}
        for suite in (
            self.testsuite_set.all()
            .prefetch_related("testcase_set")
            .annotate(test_case_avg=models.Avg("testcase__measurement"))
        ):
            results.setdefault(suite.name, {})
            results[suite.name]["measurement"] = suite.test_case_avg
            results[suite.name]["fail"] = suite.testcase_count("fail")

        return results

    def get_attribute_results(self, attributes):
        # Get attribute values per lava_scheduler_app.testjob.
        results = {}
        attributes = [x.strip() for x in attributes.split(",")]

        testdata = self.testdata_set.first()
        if testdata:
            for attr in testdata.attributes.all():
                if attr.name in attributes:
                    results[attr.name] = {}
                    results[attr.name]["fail"] = self.health != self.HEALTH_COMPLETE
                    try:
                        results[attr.name]["value"] = float(attr.value)
                    except ValueError:
                        # Ignore non-float metadata.
                        del results[attr.name]

        return results

    def get_end_datetime(self):
        return self.end_time

    def get_xaxis_attribute(self, xaxis_attribute=None):
        if not xaxis_attribute:
            return None
        with contextlib.suppress(Exception):
            testdata = self.testdata_set.first()
            if not testdata:
                return None
            data = testdata.attributes.filter(name=xaxis_attribute)
            return data.values_list("value", flat=True)[0]

    def get_metadata_dict(self):
        retval = []
        for datum in self.testdata_set.all():
            for attribute in datum.attributes.all():
                retval.append({attribute.name: attribute.value})
        return retval


class Notification(models.Model):

    TEMPLATES_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates/",
        TestJob._meta.app_label,
    )

    TEMPLATES_ENV = jinja2.Environment(  # nosec - YAML, not HTML, no XSS scope.
        loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
        extensions=["jinja2.ext.i18n"],
        autoescape=True,
    )

    DEFAULT_TEMPLATE = "testjob_notification.txt"
    DEFAULT_IRC_TEMPLATE = "testjob_irc_notification.txt"
    DEFAULT_IRC_HANDLE = "lava-bot"

    QUERY_LIMIT = 5

    test_job = models.OneToOneField(TestJob, null=False, on_delete=models.CASCADE)

    REGRESSION = 0
    PROGRESSION = 1
    TYPE_CHOICES = ((REGRESSION, "regression"), (PROGRESSION, "progression"))
    TYPE_MAP = {"regression": REGRESSION, "progression": PROGRESSION}

    type = models.IntegerField(
        choices=TYPE_CHOICES,
        default=None,
        null=True,
        blank=True,
        verbose_name=_("Type"),
    )

    VERBOSE = 0
    QUIET = 1
    STATUS_ONLY = 2
    VERBOSITY_CHOICES = (
        (VERBOSE, "verbose"),
        (QUIET, "quiet"),
        (STATUS_ONLY, "status-only"),
    )
    VERBOSITY_MAP = {"verbose": VERBOSE, "quiet": QUIET, "status-only": STATUS_ONLY}

    verbosity = models.IntegerField(choices=VERBOSITY_CHOICES, default=QUIET)

    template = models.TextField(
        default=None, null=True, blank=True, verbose_name="Template name"
    )

    blacklist = ArrayField(
        models.CharField(max_length=100, blank=True), null=True, blank=True
    )

    time_sent = models.DateTimeField(
        verbose_name=_("Time sent"), auto_now=False, auto_now_add=True, editable=False
    )

    query_owner = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Query owner",
    )

    query_name = models.TextField(
        max_length=1024, default=None, null=True, blank=True, verbose_name="Query name"
    )

    entity = models.ForeignKey(ContentType, null=True, blank=True)

    conditions = models.TextField(
        max_length=400, default=None, null=True, blank=True, verbose_name="Conditions"
    )

    def __str__(self):
        return str(self.test_job)


class NotificationRecipient(models.Model):
    class Meta:
        unique_together = ("user", "notification", "method")

    user = models.ForeignKey(
        User,
        default=None,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        verbose_name="Notification user recipient",
    )

    email = models.TextField(
        default=None, null=True, blank=True, verbose_name="recipient email"
    )

    irc_handle = models.TextField(
        default=None, null=True, blank=True, verbose_name="IRC handle"
    )

    irc_server = models.TextField(
        default=None, null=True, blank=True, verbose_name="IRC server"
    )

    notification = models.ForeignKey(
        Notification, null=False, on_delete=models.CASCADE, verbose_name="Notification"
    )

    SENT = 0
    NOT_SENT = 1
    STATUS_CHOICES = ((SENT, "sent"), (NOT_SENT, "not sent"))
    STATUS_MAP = {"sent": SENT, "not sent": NOT_SENT}

    status = models.IntegerField(
        choices=STATUS_CHOICES, default=NOT_SENT, verbose_name=_("Status")
    )

    EMAIL = 0
    EMAIL_STR = "email"
    IRC = 1
    IRC_STR = "irc"

    METHOD_CHOICES = ((EMAIL, EMAIL_STR), (IRC, IRC_STR))
    METHOD_MAP = {EMAIL_STR: EMAIL, IRC_STR: IRC}

    method = models.IntegerField(
        choices=METHOD_CHOICES, default=EMAIL, verbose_name=_("Method")
    )

    def __str__(self):
        if self.method == self.EMAIL:
            return "[email] %s (%s)" % (self.email_address, self.get_status_display())
        else:
            return "[irc] %s@%s (%s)" % (
                self.irc_handle_name,
                self.irc_server_name,
                self.get_status_display(),
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
            except Exception:
                return None

    @property
    def irc_server_name(self):
        if self.irc_server:
            return self.irc_server
        else:
            try:
                return self.user.extendeduser.irc_server
            except Exception:
                return None


class NotificationCallback(models.Model):

    notification = models.ForeignKey(
        Notification, null=False, on_delete=models.CASCADE, verbose_name="Notification"
    )

    url = models.TextField(
        default=None, null=True, blank=True, verbose_name="Callback URL"
    )

    GET = 0
    POST = 1
    METHOD_CHOICES = ((GET, "GET"), (POST, "POST"))
    METHOD_MAP = {"GET": GET, "POST": POST}

    method = models.IntegerField(
        choices=METHOD_CHOICES,
        default=None,
        null=True,
        blank=True,
        verbose_name=_("Callback method"),
    )

    token = models.TextField(
        default=None, null=True, blank=True, verbose_name="Callback token"
    )

    MINIMAL = 0
    LOGS = 1
    RESULTS = 2
    ALL = 3
    DATASET_CHOICES = (
        (MINIMAL, "minimal"),
        (LOGS, "logs"),
        (RESULTS, "results"),
        (ALL, "all"),
    )
    DATASET_MAP = {"minimal": MINIMAL, "logs": LOGS, "results": RESULTS, "all": ALL}

    dataset = models.IntegerField(
        choices=DATASET_CHOICES,
        default=None,
        null=True,
        blank=True,
        verbose_name=_("Callback dataset"),
    )

    URLENCODED = 0
    JSON = 1
    CONTENT_TYPE_CHOICES = ((URLENCODED, "urlencoded"), (JSON, "json"))
    CONTENT_TYPE_MAP = {"urlencoded": URLENCODED, "json": JSON}

    content_type = models.IntegerField(
        choices=CONTENT_TYPE_CHOICES,
        default=None,
        null=True,
        blank=True,
        verbose_name=_("Callback content-type"),
    )

    def invoke_callback(self):
        logger = logging.getLogger("lava_scheduler_app")
        data = None

        if self.method != NotificationCallback.GET:
            output = self.dataset in [
                NotificationCallback.LOGS,
                NotificationCallback.ALL,
            ]
            results = self.dataset in [
                NotificationCallback.RESULTS,
                NotificationCallback.ALL,
            ]
            data = self.notification.test_job.create_job_data(
                token=self.token, output=output, results=results
            )
            # store callback_data for later retrieval & triage
            job_data_file = os.path.join(
                self.notification.test_job.output_dir, "job_data.gz"
            )
            if data:
                # allow for jobs cancelled in submitted state
                utils.mkdir(self.notification.test_job.output_dir)
                # only write the file once
                if not os.path.exists(job_data_file):
                    with gzip.open(job_data_file, "wb") as output:
                        output.write(simplejson.dumps(data).encode("utf-8"))
        try:
            logger.info("Sending request to callback url %s" % self.url)
            headers = {}
            if self.token is not None:
                headers["Authorization"] = self.token

            if self.method == NotificationCallback.GET:
                ret = requests.get(
                    self.url, headers=headers, timeout=settings.CALLBACK_TIMEOUT
                )
            elif self.content_type == NotificationCallback.JSON:
                ret = requests.post(
                    self.url,
                    json=data,
                    headers=headers,
                    timeout=settings.CALLBACK_TIMEOUT,
                )
            else:
                ret = requests.post(
                    self.url,
                    data=data,
                    headers=headers,
                    timeout=settings.CALLBACK_TIMEOUT,
                )
            ret.raise_for_status()

        except Exception as ex:
            logger.warning("Problem sending request to %s: %s" % (self.url, ex))


class TestJobUser(models.Model):
    class Meta:
        unique_together = ("test_job", "user")
        permissions = (("cancel_resubmit_testjob", "Can cancel or resubmit test jobs"),)

    user = models.ForeignKey(User, null=False, on_delete=models.CASCADE)

    test_job = models.ForeignKey(TestJob, null=False, on_delete=models.CASCADE)

    is_favorite = models.BooleanField(default=False, verbose_name="Favorite job")

    def __str__(self):
        if self.user:
            return self.user.username
        return ""
