# Copyright (C) 2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import contextlib
import datetime
import gzip
import logging
import os
import uuid
from json import dump as json_dump

import requests
import yaml
from django.conf import settings
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField
from django.contrib.sites.models import Site
from django.core.exceptions import (
    ImproperlyConfigured,
    PermissionDenied,
    ValidationError,
)
from django.db import models, transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.html import escape
from django.utils.translation import gettext_lazy as _
from jinja2 import FileSystemLoader
from jinja2 import TemplateError as JinjaTemplateError
from jinja2.nodes import Extends as JinjaNodesExtends
from jinja2.sandbox import SandboxedEnvironment as JinjaSandboxEnv

from lava_common.decorators import nottest
from lava_common.timeout import Timeout
from lava_common.yaml import yaml_safe_dump, yaml_safe_load
from lava_results_app.utils import export_testcase
from lava_scheduler_app import environment, utils
from lava_scheduler_app.logutils import logs_instance
from lava_scheduler_app.managers import (
    GroupObjectPermissionManager,
    RestrictedDeviceQuerySet,
    RestrictedDeviceTypeQuerySet,
    RestrictedTestJobQuerySet,
    RestrictedWorkerQuerySet,
)
from lava_scheduler_app.schema import SubmissionException, validate_device
from lava_server.files import File


def auth_token():
    return get_random_string(32)


class DevicesUnavailableException(UserWarning):
    """Error raised when required number of devices are unavailable."""


class ExtendedUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    irc_handle = models.CharField(
        max_length=40, default=None, null=True, blank=True, verbose_name="IRC handle"
    )

    irc_server = models.CharField(
        max_length=40, default=None, null=True, blank=True, verbose_name="IRC server"
    )

    table_length = models.PositiveSmallIntegerField(
        verbose_name="Table length",
        help_text="leave empty for system default",
        default=None,
        null=True,
        blank=True,
    )

    def __str__(self):
        return "%s: %s@%s" % (self.user, self.irc_handle, self.irc_server)


class GroupObjectPermission(models.Model):
    objects = GroupObjectPermissionManager()

    class Meta:
        abstract = True

    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        super().full_clean()
        super().save(*args, **kwargs)

    @classmethod
    def ensure_users_group(cls, user):
        # Get or create a group that matches the users' username.
        # Then ensure that only this user is belonging to his group.
        group, _ = Group.objects.get_or_create(name=user.username)
        group.user_set.set({user}, clear=True)
        return group


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
    device_type = models.ForeignKey(
        "DeviceType", related_name="aliases", null=True, on_delete=models.CASCADE
    )

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


class RestrictedObject(models.Model):
    class Meta:
        abstract = True

    def is_permission_restricted(self, perm):
        app_label, codename = perm.split(".", 1)
        return self.permissions.filter(
            permission__content_type__app_label=app_label, permission__codename=codename
        ).exists()

    def has_any_permission_restrictions(self, perm):
        raise NotImplementedError("Should implement this")


class DeviceType(RestrictedObject):
    """
    A class of device, for example a pandaboard or a snowball.
    """

    class Meta:
        permissions = (("submit_to_devicetype", "Can submit jobs to device type"),)

    VIEW_PERMISSION = "lava_scheduler_app.view_devicetype"
    CHANGE_PERMISSION = "lava_scheduler_app.change_devicetype"
    SUBMIT_PERMISSION = "lava_scheduler_app.submit_to_devicetype"

    # Order of permission importance from most to least.
    PERMISSIONS_PRIORITY = [CHANGE_PERMISSION, SUBMIT_PERMISSION, VIEW_PERMISSION]

    objects = RestrictedDeviceTypeQuerySet.as_manager()

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
    HEALTH_DENOMINATOR_REVERSE = {"hours": HEALTH_PER_HOUR, "jobs": HEALTH_PER_JOB}
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

    def get_absolute_url(self):
        return reverse("lava.scheduler.device_type.detail", args=[self.pk])

    def can_view(self, user):
        if user.has_perm(self.VIEW_PERMISSION, self):
            return True
        if not self.is_permission_restricted(self.VIEW_PERMISSION):
            return True
        return False

    def can_change(self, user):
        return user.has_perm(self.CHANGE_PERMISSION, self)

    def has_any_permission_restrictions(self, perm):
        return self.is_permission_restricted(perm)


class Worker(RestrictedObject):
    """
    A worker node to which devices are attached.
    """

    CHANGE_PERMISSION = "lava_scheduler_app.change_worker"
    VIEW_PERMISSION = "lava_scheduler_app.view_worker"

    # Only change permission is supported for workers.
    PERMISSIONS_PRIORITY = [CHANGE_PERMISSION]

    objects = RestrictedWorkerQuerySet.as_manager()

    hostname = models.CharField(
        verbose_name=_("Hostname"),
        max_length=200,
        primary_key=True,
        default=None,
        editable=True,
    )

    STATE_ONLINE, STATE_OFFLINE = range(2)
    STATE_CHOICES = ((STATE_ONLINE, "Online"), (STATE_OFFLINE, "Offline"))
    STATE_REVERSE = {"Online": STATE_ONLINE, "Offline": STATE_OFFLINE}
    state = models.IntegerField(
        choices=STATE_CHOICES, default=STATE_OFFLINE, editable=False
    )

    HEALTH_ACTIVE, HEALTH_MAINTENANCE, HEALTH_RETIRED = range(3)
    HEALTH_CHOICES = (
        (HEALTH_ACTIVE, "Active"),
        (HEALTH_MAINTENANCE, "Maintenance"),
        (HEALTH_RETIRED, "Retired"),
    )
    HEALTH_REVERSE = {
        "Active": HEALTH_ACTIVE,
        "Maintenance": HEALTH_MAINTENANCE,
        "Retired": HEALTH_RETIRED,
    }
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

    job_limit = models.PositiveIntegerField(default=0)

    version = models.CharField(
        verbose_name=_("Dispatcher version"),
        max_length=50,
        null=True,
        default=None,
        blank=True,
    )

    token = models.CharField(
        max_length=32, default=auth_token, help_text=_("Authorization token")
    )

    def __str__(self):
        return self.hostname

    def get_absolute_url(self):
        return reverse("lava.scheduler.worker.detail", args=[self.pk])

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

    def can_change(self, user):
        if user.username == "lava-health":
            return True
        return user.has_perm(self.CHANGE_PERMISSION, self)

    def has_any_permission_restrictions(self, perm):
        return self.is_permission_restricted(perm)


class Device(RestrictedObject):
    """
    A device that we can run tests on.
    """

    class Meta:
        permissions = (("submit_to_device", "Can submit jobs to device"),)

    VIEW_PERMISSION = "lava_scheduler_app.view_device"
    CHANGE_PERMISSION = "lava_scheduler_app.change_device"
    SUBMIT_PERMISSION = "lava_scheduler_app.submit_to_device"

    # This maps the corresponding permissions for 'parent' dependencies.
    DEVICE_TYPE_PERMISSION_MAP = {
        VIEW_PERMISSION: DeviceType.VIEW_PERMISSION,
        CHANGE_PERMISSION: DeviceType.CHANGE_PERMISSION,
        SUBMIT_PERMISSION: DeviceType.SUBMIT_PERMISSION,
    }

    # Order of permission importance from most to least.
    PERMISSIONS_PRIORITY = [CHANGE_PERMISSION, SUBMIT_PERMISSION, VIEW_PERMISSION]

    objects = RestrictedDeviceQuerySet.as_manager()

    hostname = models.CharField(
        verbose_name=_("Hostname"),
        max_length=200,
        primary_key=True,
        editable=True,  # read-only after create via admin.py
    )

    device_type = models.ForeignKey(
        DeviceType, verbose_name=_("Device type"), on_delete=models.CASCADE
    )

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
        on_delete=models.CASCADE,
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
    STATE_REVERSE = {
        "Idle": STATE_IDLE,
        "Reserved": STATE_RESERVED,
        "Running": STATE_RUNNING,
    }
    state = models.IntegerField(
        choices=STATE_CHOICES, default=STATE_IDLE, editable=False
    )

    # The device health helps to decide what to do next with the device
    (
        HEALTH_GOOD,
        HEALTH_UNKNOWN,
        HEALTH_LOOPING,
        HEALTH_BAD,
        HEALTH_MAINTENANCE,
        HEALTH_RETIRED,
    ) = range(6)
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

    is_synced = models.BooleanField(
        default=False,
        help_text=("Is this device synced from device dictionary or manually created."),
    )

    def __str__(self):
        return "%s (%s, health %s)" % (
            self.hostname,
            self.get_state_display(),
            self.get_health_display(),
        )

    def current_job(self):
        # This method will use the 'running_jobs' attribute if present which
        # is a prefetch_related attribute containing non-finished jobs
        # ie. Prefetch('testjobs', queryset=TestJob.objects.filter(~Q(state=TestJob.STATE_FINISHED)), to_attr='running_jobs')
        try:
            return self.running_jobs[0]
        except AttributeError:
            try:
                return self.testjobs.select_related("submitter").get(
                    ~Q(state=TestJob.STATE_FINISHED)
                )
            except TestJob.DoesNotExist:
                return None
        except IndexError:
            return None

    def get_absolute_url(self):
        return reverse("lava.scheduler.device.detail", args=[self.pk])

    def get_simple_state_display(self):
        if self.state == Device.STATE_IDLE:
            if self.health in [Device.HEALTH_MAINTENANCE, Device.HEALTH_RETIRED]:
                return self.get_health_display()
        return self.get_state_display()

    def has_any_permission_restrictions(self, perm):
        if not self.is_permission_restricted(perm):
            return self.device_type.has_any_permission_restrictions(
                self.DEVICE_TYPE_PERMISSION_MAP[perm]
            )
        else:
            return True

    def can_view(self, user):
        """
        Checks if this device is visible to the specified user.
        Retired devices are deemed to be visible - filter these out
        explicitly where necessary.
        :param user: User trying to view the device
        :return: True if the user can see this device
        """
        if user.has_perm(self.VIEW_PERMISSION, self):
            return True
        if not self.is_permission_restricted(self.VIEW_PERMISSION):
            if self.device_type.can_view(user):
                return True
        return False

    def can_change(self, user):
        if user.has_perm(self.CHANGE_PERMISSION, self):
            return True
        if not self.is_permission_restricted(self.CHANGE_PERMISSION):
            if user.has_perm(self.device_type.CHANGE_PERMISSION, self.device_type):
                return True
        return False

    def can_submit(self, user):
        if self.health == Device.HEALTH_RETIRED:
            return False
        if user.username == "lava-health":
            return True
        if user.has_perm(self.SUBMIT_PERMISSION, self):
            return True
        if not self.is_permission_restricted(self.SUBMIT_PERMISSION):
            if not self.device_type.is_permission_restricted(
                DeviceType.SUBMIT_PERMISSION
            ):
                if user.is_authenticated:
                    return True
            elif user.has_perm(self.device_type.SUBMIT_PERMISSION, self.device_type):
                return True

        return False

    def is_valid(self):
        try:
            rendered = self.load_configuration()
            validate_device(rendered)
        except (SubmissionException, yaml.YAMLError) as exc:
            logger = logging.getLogger("lava-scheduler")
            logger.error(
                "Error validating device configuration for %s: %s",
                self.hostname,
                str(exc),
            )
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
            pk = job.pk
            if job.sub_jobs_list:
                pk = job.sub_id
            verbose_name = job._meta.verbose_name.capitalize()
            job_url = '<a href="%s" title="%s summary">%s</a>' % (
                job.get_absolute_url(),
                escape(verbose_name),
                escape(pk),
            )

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
                            % (prev_health_display, self.get_health_display(), job_url),
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
                        % (
                            prev_health_display,
                            self.get_health_display(),
                            job_url,
                            msg,
                        ),
                    )
            elif infrastructure_error:
                self.health = Device.HEALTH_UNKNOWN
                self.log_admin_entry(
                    None,
                    "%s → %s (Infrastructure error after %s)"
                    % (prev_health_display, self.get_health_display(), job_url),
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
            # Only update health of devices in good
            if self.health != Device.HEALTH_GOOD:
                return
            self.log_admin_entry(
                user, "%s → Unknown (worker going active)" % self.get_health_display()
            )
            self.health = Device.HEALTH_UNKNOWN

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
            with contextlib.suppress(OSError):
                return File("device", self.hostname).read()
            return None

        try:
            template = environment.devices().get_template("%s.jinja2" % self.hostname)
            device_template = template.render(**job_ctx)
        except JinjaTemplateError:
            return None

        if output_format == "yaml":
            return device_template
        else:
            return yaml_safe_load(device_template)

    def minimise_configuration(self, data):
        """
        Support for dynamic connections which only require
        critical elements of device configuration.
        Principally drop top level parameters and commands
        like power.
        """

        def get(data, keys):
            for key in keys:
                data = data.get(key, {})
            return data

        data["constants"]["kernel-start-message"] = ""
        device_configuration = {
            "hostname": self.hostname,
            "constants": data.get("constants", {}),
            "timeouts": data.get("timeouts", {}),
            "actions": {
                "deploy": {
                    "connections": get(data, ["actions", "deploy", "connections"]),
                    "methods": get(data, ["actions", "deploy", "methods"]),
                },
                "boot": {
                    "connections": get(data, ["actions", "boot", "connections"]),
                    "methods": get(data, ["actions", "boot", "methods"]),
                },
            },
        }
        return device_configuration

    def save_configuration(self, data):
        try:
            File("device", self.hostname).write(data)
            return True
        except OSError as exc:
            logger = logging.getLogger("lava-scheduler")
            logger.error(
                "Error saving device configuration for %s: %s", self.hostname, str(exc)
            )
            return False

    def get_extends(self):
        jinja_config = self.load_configuration(output_format="raw")
        if not jinja_config:
            return None

        env = JinjaSandboxEnv(autoescape=False)
        try:
            ast = env.parse(jinja_config)
            extends = list(ast.find_all(JinjaNodesExtends))
            if len(extends) != 1:
                logger = logging.getLogger("lava-scheduler")
                logger.error("Found %d extends for %s", len(extends), self.hostname)
                return None
            else:
                return os.path.splitext(extends[0].template.value)[0]
        except JinjaTemplateError as exc:
            logger = logging.getLogger("lava-scheduler")
            logger.error("Invalid template for %s: %s", self.hostname, str(exc))
            return None

    def get_health_check(self):
        # Get the device dictionary
        extends = self.get_extends()
        if not extends:
            return None

        filename = os.path.join(settings.HEALTH_CHECKS_PATH, "%s.yaml" % extends)
        # Try if health check file is having a .yml extension
        if not os.path.exists(filename):
            filename = os.path.join(settings.HEALTH_CHECKS_PATH, "%s.yml" % extends)
        try:
            with open(filename) as f_in:
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


def _check_submit_to_devices(device_list, user):
    """
    Handles the affects of Device Permissions on job submission
    :param device_list: A device queryset to check
    :param user: The user submitting the job
    :return: a subset of the device_list to which the user
    is allowed to submit a TestJob.
    :raise: DevicesUnavailableException if none of the
    devices in device_list are available for submission by this user.
    """
    allow = []
    if not device_list.exists():
        return allow
    allow = list(device_list.accessible_by_user(user, Device.SUBMIT_PERMISSION))
    if not allow:
        raise DevicesUnavailableException(
            "No devices from %s pool are currently available to user %s"
            % (list(device_list.values_list("hostname", flat=True)), user)
        )
    return allow


def _check_tags_support(tag_devices, device_list, count=1):
    """
    Combines the Device Ownership list with the requested tag list and
    returns any devices which meet both criteria.
    If neither the job nor the device have any tags, tag_devices will
    be empty, so the check will pass.
    :param tag_devices: A list of devices which meet the tag
    requirements
    :param device_list: A list of devices to which the user is able
    to submit a TestJob
    :param count: The number of requested devices
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
    logger = logging.getLogger("lava-scheduler")
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

    if not device_type.can_view(user):
        msg = "Device type '%s' is unavailable to user '%s'" % (name, user.username)
        logger.error(msg)
        raise DevicesUnavailableException(msg)
    return device_type


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

    if not orig:
        orig = yaml_safe_dump(job_data)

    is_public = False
    viewing_groups = []
    param = job_data["visibility"]
    if isinstance(param, str):
        if param == "public":
            is_public = True
        else:
            group, _ = Group.objects.get_or_create(name=user.username)
            viewing_groups = [group]
    elif isinstance(param, dict):
        if "group" in param:
            viewing_groups = list(Group.objects.filter(name__in=param["group"]))
            if not viewing_groups:
                raise SubmissionException(
                    "No known groups were found in the visibility list."
                )

    # handle queue timeout.
    queue_timeout = None
    if "timeouts" in job_data and "queue" in job_data["timeouts"]:
        queue_timeout = Timeout.parse(job_data["timeouts"]["queue"])

    with transaction.atomic():
        job = TestJob(
            definition=yaml_safe_dump(job_data),
            original_definition=orig,
            submitter=user,
            requested_device_type=device_type,
            target_group=target_group,
            description=job_data["job_name"],
            health_check=health_check,
            priority=priority,
            is_public=is_public,
            queue_timeout=queue_timeout,
        )
        job.save()

        # need a valid job (with a primary_key) before tags and groups can be
        # assigned
        job.tags.add(*taglist)
        job.viewing_groups.add(*viewing_groups)

    return job


def _pipeline_protocols(job_data, user, yaml_data=None):
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
        yaml_data = yaml_safe_dump(job_data)
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

                device_list = Device.objects.filter(
                    Q(device_type=device_type), ~Q(health=Device.HEALTH_RETIRED)
                )
                allowed_devices = _check_submit_to_devices(device_list, user)

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
        # track the zero id job as the parent of the group in the sub_id text field
        parent = None
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
                    yaml_data  # store complete submission, inc. comments
                )
                job.save()
                job_object_list.append(job)

        return job_object_list


@nottest
class TestJob(models.Model):
    """
    A test job is a test process that will be run on a Device.
    """

    class Meta:
        index_together = ["health", "state", "requested_device_type"]
        default_permissions = ("change", "delete")
        indexes = (
            models.Index(fields=("-submit_time",)),
            models.Index(fields=("-start_time",)),
            models.Index(fields=("-end_time",)),
            models.Index(
                name="device_type_jobs_index",
                fields=("requested_device_type", "-submit_time"),
            ),
            models.Index(
                name="device_jobs_index", fields=("actual_device", "-submit_time")
            ),
            models.Index(
                name="current_job_prefetch_index",
                fields=("actual_device",),
                condition=(
                    ~Q(state=5)  # HACK: refers to TestJob.STATE_FINISHED
                    & Q(actual_device__isnull=False)
                ),
            ),
            models.Index(
                fields=("requested_device_type", "id"),
                name="job_queued_per_device_type_idx",
                condition=Q(state=0),  # HACK: refers to TestJob.STATE_SUBMITTED
            ),
            models.Index(
                name="health_checks_count_idx",
                fields=("requested_device_type", "-submit_time", "id", "health"),
                condition=Q(health_check=True),
            ),
        )

    # Permission strings. Not real permissions.
    VIEW_PERMISSION = "lava_scheduler_app.view_testjob"
    CHANGE_PERMISSION = "lava_scheduler_app.change_testjob"
    # This maps the corresponding permissions for 'parent' dependencies.
    DEVICE_PERMISSION_MAP = {
        VIEW_PERMISSION: Device.VIEW_PERMISSION,
        CHANGE_PERMISSION: Device.CHANGE_PERMISSION,
    }
    DEVICE_TYPE_PERMISSION_MAP = {
        VIEW_PERMISSION: DeviceType.VIEW_PERMISSION,
        CHANGE_PERMISSION: DeviceType.CHANGE_PERMISSION,
    }

    objects = RestrictedTestJobQuerySet.as_manager()

    NOTIFY_EMAIL_METHOD = "email"
    NOTIFY_IRC_METHOD = "irc"

    id = models.AutoField(primary_key=True)

    sub_id = models.CharField(verbose_name=_("Sub ID"), blank=True, max_length=200)

    is_public = models.BooleanField(default=False)

    target_group = models.CharField(
        verbose_name=_("Target Group"),
        blank=True,
        max_length=64,
        null=True,
        default=None,
    )

    submitter = models.ForeignKey(
        User, verbose_name=_("Submitter"), related_name="+", on_delete=models.CASCADE
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
        DeviceType,
        null=True,
        default=None,
        related_name="+",
        blank=True,
        on_delete=models.CASCADE,
    )

    @property
    def dynamic_connection(self):
        """
        Secondary connection detection - multinode only.
        A Primary connection needs a real device (persistence).
        """
        if not self.is_multinode or not self.definition:
            return False
        job_data = yaml_safe_load(self.definition)
        return "connection" in job_data

    tags = models.ManyToManyField(Tag, blank=True)

    # This is set once the job starts or is reserved.
    actual_device = models.ForeignKey(
        Device,
        null=True,
        default=None,
        related_name="testjobs",
        blank=True,
        on_delete=models.CASCADE,
    )

    submit_time = models.DateTimeField(
        verbose_name=_("Submit time"),
        auto_now=False,
        auto_now_add=True,
        db_index=False,  # Descending index defined in Meta
    )
    start_time = models.DateTimeField(
        verbose_name=_("Start time"),
        auto_now=False,
        auto_now_add=False,
        null=True,
        blank=True,
        editable=False,
        db_index=False,  # Descending index defined in Meta
    )
    end_time = models.DateTimeField(
        verbose_name=_("End time"),
        auto_now=False,
        auto_now_add=False,
        null=True,
        blank=True,
        editable=False,
        db_index=False,  # Descending index defined in Meta
    )

    @property
    def duration(self):
        if self.end_time is None or self.start_time is None:
            return None
        # Only return seconds and not milliseconds
        seconds = (self.end_time - self.start_time).total_seconds()
        return datetime.timedelta(seconds=int(seconds))

    (
        STATE_SUBMITTED,
        STATE_SCHEDULING,
        STATE_SCHEDULED,
        STATE_RUNNING,
        STATE_CANCELING,
        STATE_FINISHED,
    ) = range(6)
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
        The jobs has been scheduled on the given device.
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
        The job was canceled by a user.
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

        # If the job is really quick to finish (a failure in validate), and
        # lava-master is slow to response then lava-logs will notice the end of
        # a job (and call go_state_finished) before lava-master handles the
        # START_OK message (and call go_state_running).
        # In this case, self.start_time would be None.
        now = timezone.now()
        if self.start_time is None:
            self.start_time = now
        self.end_time = now

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

    queue_timeout = models.BigIntegerField(
        verbose_name=_("Queue timeout"), null=True, blank=True, editable=False
    )

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

    token = models.CharField(
        max_length=32, default=auth_token, help_text=_("Authorization token")
    )

    @property
    def results_link(self):
        return reverse("lava.results.testjob", args=[self.id])

    @property
    def essential_role(self):
        if not self.is_multinode:
            return False
        data = yaml_safe_load(self.definition)
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
    def device_role(self):
        if not self.is_multinode:
            return "Error"
        try:
            data = yaml_safe_load(self.definition)
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
        r = f"{self.get_state_display()} ({self.get_health_display()}) {job_type} job"
        if self.actual_device_id:
            r += f" on {self.actual_device_id}"
        elif self.requested_device_type_id:
            r += f" for {self.requested_device_type_id}"
        r += f" ({self.id})"
        return r

    def get_absolute_url(self):
        return reverse("lava.scheduler.job.detail", args=[self.display_id])

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
        job_data = yaml_safe_load(yaml_data)

        # visibility checks
        if "visibility" not in job_data:
            raise SubmissionException("Job visibility must be specified.")

        # pipeline protocol handling, e.g. lava-multinode
        job_list = _pipeline_protocols(job_data, user, yaml_data)
        if job_list:
            # explicitly a list, not a QuerySet.
            return job_list
        # singlenode only
        device_type = _get_device_type(user, job_data["device_type"])
        devices = Device.objects.filter(
            Q(device_type=device_type), ~Q(health=Device.HEALTH_RETIRED)
        )
        allow = _check_submit_to_devices(devices, user)
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

    def can_view(self, user):
        if user == self.submitter or user.is_superuser:
            return True
        if self.viewing_groups.exists():
            # If viewing_groups is set, user must belong to all the specified
            # groups.
            return set(self.viewing_groups.all()).issubset(set(user.groups.all()))
        if self.is_public:
            if self.actual_device:
                return self.actual_device.can_view(user)
            if self.requested_device_type:
                return self.requested_device_type.can_view(user)
            # For secondary connection requested_device_type is None, so check
            # the group jobs.
            if self.is_multinode:
                sub_jobs = self.sub_jobs_list
                sub_jobs = sub_jobs.filter(requested_device_type__isnull=False)
                sub_jobs = sub_jobs.select_related("submitter")
                for sub_job in sub_jobs:
                    if not sub_job.can_view(user):
                        return False
            return True

        return False

    def can_change(self, user):
        if user == self.submitter:
            return True

        if self.actual_device:
            return self.actual_device.can_change(user)
        elif user.has_perm(DeviceType.CHANGE_PERMISSION, self.requested_device_type):
            return True

        return False

    def can_change_priority(self, user):
        """
        Permission and state required to change job priority.
        Multinode jobs cannot have their priority changed.
        """
        if user == self.submitter:
            return True
        if self.can_change(user):
            return True

        return False

    def can_annotate(self, user):
        """
        Permission required for user to add failure information to a job
        """
        if not self.state == TestJob.STATE_FINISHED:
            return False
        if not self.can_change(user):
            return False

        return True

    def can_cancel(self, user):
        states = [
            TestJob.STATE_SUBMITTED,
            TestJob.STATE_SCHEDULING,
            TestJob.STATE_SCHEDULED,
            TestJob.STATE_RUNNING,
        ]
        can_cancel = self.can_change(user) or user.has_perm(
            "lava_scheduler_app.change_testjob"
        )
        return can_cancel and self.state in states

    def can_resubmit(self, user):
        if self.can_change(user) or user.has_perm("lava_scheduler_app.change_testjob"):
            return True

        # Allow users who are able to submit to device or devicetype to also
        # resubmit jobs.
        if self.actual_device:
            return self.actual_device.can_submit(user)
        elif user.has_perm(DeviceType.SUBMIT_PERMISSION, self.requested_device_type):
            return True

        return False

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
        if output:
            with contextlib.suppress(OSError):
                data["log"] = logs_instance.read(self)

        # Results.
        if results:
            data["results"] = {}
            for test_suite in self.testsuite_set.all():
                yaml_list = []
                for test_case in test_suite.testcase_set.all():
                    yaml_list.append(export_testcase(test_case))
                data["results"][test_suite.name] = yaml_safe_dump(yaml_list)

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

    def dynamic_jobs(self):
        if not self.is_multinode:
            return []
        try:
            data = yaml_safe_load(self.definition)
        except yaml.YAMLError:
            return []
        try:
            role = data["protocols"]["lava-multinode"]["role"]
        except (KeyError, TypeError):
            return []

        for job in self.sub_jobs_list:
            if job == self:
                continue
            try:
                sub_data = yaml_safe_load(job.definition)
            except yaml.YAMLError:
                continue
            if not "connection" in sub_data:
                continue
            if role == sub_data.get("host_role"):
                yield job

    def dynamic_host(self):
        if self.actual_device is not None:
            return self.actual_device.worker_host

        try:
            data = yaml_safe_load(self.definition)
        except yaml.YAMLError:
            return None
        host_role = data.get("host_role")
        if not host_role:
            return None

        for job in self.sub_jobs_list:
            if job == self:
                continue
            try:
                data = yaml_safe_load(job.definition)
            except yaml.YAMLError:
                continue
            role = data.get("protocols", {}).get("lava-multinode", {}).get("role")
            if role == host_role:
                return job
        return None

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

        if hasattr(self, "testdata"):
            for attr in self.testdata.attributes.all():
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
            if not hasattr(self, "testdata"):
                return None
            data = self.testdata.attributes.filter(name=xaxis_attribute)
            return data.values_list("value", flat=True)[0]

    def get_metadata_dict(self):
        retval = []
        if hasattr(self, "testdata"):
            for attribute in self.testdata.attributes.all():
                retval.append({attribute.name: attribute.value})
        return retval

    @transaction.atomic
    def cancel(self, user):
        if not self.can_cancel(user):
            if self.state in [TestJob.STATE_CANCELING, TestJob.STATE_FINISHED]:
                # Don't do anything for jobs that ended already
                return
            raise PermissionDenied("Insufficient permissions")
        if self.is_multinode:
            multinode_jobs = TestJob.objects.select_for_update().filter(
                target_group=self.target_group
            )
            for multinode_job in multinode_jobs:
                multinode_job.go_state_canceling()
                multinode_job.save()
        else:
            self.go_state_canceling()
            self.save()


class Notification(models.Model):
    TEMPLATES_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates/",
        TestJob._meta.app_label,
    )

    TEMPLATES_ENV = JinjaSandboxEnv(
        loader=FileSystemLoader(TEMPLATES_DIR),
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

    entity = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.CASCADE
    )

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
    header = models.CharField(
        default="Authorization", max_length=64, verbose_name="Header name"
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
        logger = logging.getLogger("lava-scheduler")
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
                    with gzip.open(job_data_file, "wt") as output:
                        json_dump(data, output)
        try:
            logger.info("Sending request to callback url %s" % self.url)
            headers = {}
            if self.token is not None:
                headers[self.header] = self.token

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


@nottest
class TestJobUser(models.Model):
    class Meta:
        unique_together = ("test_job", "user")

    user = models.ForeignKey(User, null=False, on_delete=models.CASCADE)

    test_job = models.ForeignKey(TestJob, null=False, on_delete=models.CASCADE)

    is_favorite = models.BooleanField(default=False, verbose_name="Favorite job")

    def __str__(self):
        if self.user:
            return self.user.username
        return ""


class GroupDeviceTypePermission(GroupObjectPermission):
    class Meta:
        unique_together = ("group", "permission", "devicetype")

    devicetype = models.ForeignKey(
        DeviceType, null=False, on_delete=models.CASCADE, related_name="permissions"
    )

    def __str__(self):
        return "Permission '%s' for device type %s" % (
            self.permission.codename,
            self.devicetype,
        )


class GroupDevicePermission(GroupObjectPermission):
    class Meta:
        unique_together = ("group", "permission", "device")

    device = models.ForeignKey(
        Device, null=False, on_delete=models.CASCADE, related_name="permissions"
    )

    def __str__(self):
        return "Permission '%s' for device %s" % (self.permission.codename, self.device)


class GroupWorkerPermission(GroupObjectPermission):
    class Meta:
        unique_together = ("group", "permission", "worker")

    worker = models.ForeignKey(
        Worker, null=False, on_delete=models.CASCADE, related_name="permissions"
    )

    def __str__(self):
        return "Permission '%s' for worker %s" % (self.permission.codename, self.worker)


class RemoteArtifactsAuth(models.Model):
    class Meta:
        unique_together = ("name", "user")
        ordering = ["name"]

    user = models.ForeignKey(
        User, null=False, on_delete=models.CASCADE, verbose_name="User"
    )

    name = models.CharField(max_length=100, null=False, verbose_name=_("Token name"))
    token = models.CharField(max_length=100, null=False, verbose_name=_("Token value"))

    def __str__(self):
        return self.name
