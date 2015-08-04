# pylint: disable=too-many-lines

import logging
import os
import uuid
import jinja2
import simplejson
import urlparse
import smtplib
import socket
import sys
import yaml
from django.conf import settings
from django.contrib.auth.models import User, Group
from django.contrib.sites.models import Site
from django.utils.safestring import mark_safe
from django.core.exceptions import (
    ImproperlyConfigured,
    ValidationError,
    ObjectDoesNotExist,
    MultipleObjectsReturned,
)
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import models
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _
from django.shortcuts import get_object_or_404
from django_kvstore import models as kvmodels
from django_kvstore import get_kvstore
from django.utils import timezone

from django_restricted_resource.models import RestrictedResource

from dashboard_app.models import Bundle, BundleStream

from lava_dispatcher.job import validate_job_data
from lava_scheduler_app import utils

from linaro_django_xmlrpc.models import AuthToken

# pylint: disable=invalid-name,no-self-use,too-many-public-methods,too-few-public-methods

# Make the open function accept encodings in python < 3.x
if sys.version_info[0] < 3:
    import codecs
    open = codecs.open  # pylint: disable=redefined-builtin


class JSONDataError(ValueError):
    """Error raised when JSON is syntactically valid but ill-formed."""


class DevicesUnavailableException(UserWarning):
    """Error raised when required number of devices are unavailable."""


class SubmissionException(UserWarning):
    """ Error raised if the submission is itself invalid. """


class Tag(models.Model):

    name = models.SlugField(unique=True)

    description = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return self.name


def validate_job_json(data):
    try:
        ob = simplejson.loads(data)
        validate_job_data(ob)
    except ValueError, e:
        raise ValidationError(e)


class Architecture(models.Model):
    name = models.CharField(
        primary_key=True,
        verbose_name=u'Architecture version',
        help_text=u'e.g. ARMv7',
        max_length=100,
        editable=True,
    )

    def __unicode__(self):
        return self.pk


class ProcessorFamily(models.Model):
    name = models.CharField(
        primary_key=True,
        verbose_name=u'Processor Family',
        help_text=u'e.g. OMAP4, Exynos',
        max_length=100,
        editable=True,
    )

    def __unicode__(self):
        return self.pk


class BitWidth(models.Model):
    width = models.PositiveSmallIntegerField(
        primary_key=True,
        verbose_name=u'Processor bit width',
        help_text=u'integer: e.g. 32 or 64',
        editable=True,
    )

    def __unicode__(self):
        return "%d" % self.pk


class Core(models.Model):
    name = models.CharField(
        primary_key=True,
        verbose_name=u'CPU core',
        help_text=u'Name of a specific CPU core, e.g. Cortex-A9',
        editable=True,
        max_length=100,
    )

    def __unicode__(self):
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
    )

    processor = models.ForeignKey(
        ProcessorFamily,
        related_name='device_types',
        blank=True,
        null=True,
    )

    cpu_model = models.CharField(
        verbose_name=u'CPU model',
        help_text=u'e.g. a list of CPU model descriptive strings: OMAP4430 / OMAP4460',
        max_length=100,
        blank=True,
        null=True,
        editable=True,
    )

    bits = models.ForeignKey(
        BitWidth,
        related_name='device_types',
        blank=True,
        null=True,
    )

    cores = models.ManyToManyField(
        Core,
        related_name='device_types',
        blank=True,
        null=True,
    )

    core_count = models.PositiveSmallIntegerField(
        verbose_name=u'Total number of cores',
        help_text=u'Must be an equal number of each type(s) of core(s).',
        blank=True,
        null=True,
    )

    def __unicode__(self):
        return self.name

    description = models.TextField(
        verbose_name=_(u"Device Type Description"),
        max_length=200,
        null=True,
        blank=True,
        default=None
    )

    health_check_job = models.TextField(
        null=True, blank=True, default=None, validators=[validate_job_json])

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

    def devices_visible_to(self, user):
        """
        Prepare a list of devices of this DeviceType which
        this user can see. If the DeviceType is not hidden,
        returns all devices of this type.
        :param user: User to check
        :return: a list of devices of this DeviceType which the
        user can see. The list may be empty if the type is hidden
        and the user owns none of the devices of this type.
        """
        q = list(Device.objects.filter(device_type=self))
        if self.owners_only:
            return [o for o in q if o.is_owned_by(user)]
        else:
            return q


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


class Worker(models.Model):
    """
    A worker node to which devices are attached.
    """

    hostname = models.CharField(
        verbose_name=_(u"Hostname"),
        max_length=200,
        primary_key=True,
        default=None,
        editable=False
    )

    rpc2_url = models.CharField(
        verbose_name=_(u"Master RPC2 URL"),
        max_length=200,
        null=True,
        blank=True,
        editable=True,
        default=None,
        help_text=("Corresponds to the master node's RPC2 url. Does not have"
                   " any impact when set on a worker node.")
    )

    display = models.BooleanField(
        default=True,
        help_text=("Should this be displayed in the GUI or not. This will be"
                   " useful when a worker needs to be removed but still"
                   " linked device status transitions and devices should be"
                   " intact."))

    ip_address = models.CharField(
        verbose_name=_(u"IP Address"),
        max_length=20,
        null=True,
        blank=True,
        editable=False,
        default=None
    )

    is_master = models.BooleanField(
        verbose_name=_(u"Is Master?"),
        default=False,
        editable=True
    )

    description = models.TextField(
        verbose_name=_(u"Worker Description"),
        max_length=200,
        null=True,
        blank=True,
        default=None,
        editable=True
    )

    uptime = models.CharField(
        verbose_name=_(u"Host Uptime"),
        max_length=200,
        null=True,
        blank=True,
        default=None,
        editable=False
    )

    arch = models.CharField(
        verbose_name=_(u"Architecture"),
        max_length=200,
        null=True,
        blank=True,
        default=None,
        editable=False
    )

    platform = models.CharField(
        verbose_name=_(u"Platform"),
        max_length=200,
        null=True,
        blank=True,
        default=None,
        editable=False
    )

    hardware_info = models.TextField(
        verbose_name=_(u"Complete Hardware Information"),
        editable=False,
        blank=True
    )

    software_info = models.TextField(
        verbose_name=_(u"Complete Software Information"),
        editable=False,
        blank=True
    )

    last_heartbeat = models.DateTimeField(
        verbose_name=_(u"Last Heartbeat"),
        auto_now=False,
        auto_now_add=False,
        null=True,
        blank=True,
        editable=False
    )

    last_master_scheduler_tick = models.DateTimeField(
        verbose_name=_(u"Last Master Scheduler Tick"),
        auto_now=False,
        auto_now_add=False,
        null=True,
        blank=True,
        editable=False,
        help_text=("Corresponds to the master node's last scheduler tick. "
                   "Does not have any impact when set on a worker node.")
    )

    def __unicode__(self):
        return self.hostname

    def can_admin(self, user):
        if user.has_perm('lava_scheduler_app.change_worker'):
            return True
        else:
            return False

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
        return mark_safe(self.description)

    def get_hardware_info(self):
        return mark_safe(self.hardware_info)

    def get_software_info(self):
        return mark_safe(self.software_info)

    def too_long_since_last_heartbeat(self):
        """Calculates if the last_heartbeat is more than the heartbeat_timeout
        specified in seconds.

        If there is a delay return True else False.
        """
        if self.last_heartbeat is None:
            return False

        difference = timezone.now() - self.last_heartbeat

        # We deliberately add a 10% delay to scheduler tick in order to account
        # for network, processing, etc., overheads.
        scheduler_tick = timezone.now() - self.master_scheduler_tick()
        scheduler_tick = scheduler_tick.total_seconds()
        scheduler_tick = scheduler_tick + (scheduler_tick * 0.1)

        # scheduler_tick is added here to account for the time scheduler daemon
        # process gets back to the next loop.
        # Added since we observe offline worker in the UI which uses the same
        # API to display offline workers.
        heartbeat_timeout = utils.get_heartbeat_timeout() + scheduler_tick
        if difference.total_seconds() > heartbeat_timeout:
            return True
        else:
            return False

    def attached_devices(self):
        return Device.objects.filter(worker_host=self)

    def update_description(self, description):
        self.description = description
        self.save()

    @classmethod
    def update_heartbeat(cls, heartbeat_data):
        heartbeat_data = simplejson.loads(heartbeat_data)
        info_size = heartbeat_data.get('info_size', None)
        hostname = heartbeat_data.get('hostname', None)
        devices = heartbeat_data.get('devices', None)

        worker, created = Worker.objects.get_or_create(hostname=hostname)
        worker.uptime = heartbeat_data.get('uptime', None)
        worker.last_heartbeat = timezone.now()

        if info_size and info_size == 'complete':
            worker.arch = heartbeat_data.get('arch', None)
            worker.hardware_info = heartbeat_data.get('hardware_info', "")
            worker.software_info = heartbeat_data.get('software_info', "")
            worker.platform = heartbeat_data.get('platform', None)
            worker.ip_address = heartbeat_data.get('ipaddr', None)

        if worker:
            worker.save()
            for d in devices:
                try:
                    device = Device.objects.get(hostname=d)
                    device.worker_host = worker
                    device.save()
                except Device.DoesNotExist:
                    continue
            return True
        else:
            return False

    def on_master(self):
        return self.is_master

    @classmethod
    def get_master(cls):
        """Returns the master node.
        """
        try:
            worker = Worker.objects.get(is_master=True)
            return worker
        except:
            raise ValueError("Unable to find master node")

    @classmethod
    def get_rpc2_url(cls):
        """Returns the RPC2 URL of master node.
        """
        master = Worker.get_master()
        return master.rpc2_url

    @classmethod
    def localhost(cls):
        """Return self ie., the current worker object.
        """
        try:
            localhost = Worker.objects.get(hostname=utils.get_fqdn())
            return localhost
        except Worker.DoesNotExist:
            raise ValueError("Worker node unavailable")

    @classmethod
    def record_last_master_scheduler_tick(self):
        """Records the master's last scheduler tick timestamp.
        """
        master = Worker.get_master()
        master.last_master_scheduler_tick = timezone.now()
        master.save()

    def master_scheduler_tick(self):
        """Returns django.utils.timezone object of master's last scheduler tick
        timestamp. If the master's last scheduler tick is not yet recorded
        return the current timestamp.
        """
        master = Worker.get_master()
        if master.last_master_scheduler_tick:
            return master.last_master_scheduler_tick
        else:
            return timezone.now()


class DeviceDictionaryTable(models.Model):
    kee = models.CharField(max_length=255)
    value = models.TextField()

    def __unicode__(self):
        return self.kee.replace('__KV_STORE_::lava_scheduler_app.models.DeviceDictionary:', '')

    def lookup_device_dictionary(self):
        val = self.kee
        msg = val.replace('__KV_STORE_::lava_scheduler_app.models.DeviceDictionary:', '')
        return DeviceDictionary.get(msg)


class ExtendedKVStore(kvmodels.Model):
    """
    Enhanced kvstore Model which allows to set the kvstore as a class variable
    """
    kvstore = None

    def save(self):
        d = self.to_dict()
        self.kvstore.set(kvmodels.generate_key(self.__class__, self._get_pk_value()), d)

    def delete(self):
        self.kvstore.delete(kvmodels.generate_key(self.__class__, self._get_pk_value()))

    @classmethod
    def get(cls, kvstore_id):
        fields = cls.kvstore.get(kvmodels.generate_key(cls, kvstore_id))
        if fields is None:
            return None
        return cls.from_dict(fields)

    @classmethod
    def object_list(cls):
        """
        Not quite the same as a Django QuerySet, just a simple list of all entries.
        Use the to_dict() method on each item in the list to see the key value pairs.
        """
        return [kv.lookup_device_dictionary() for kv in DeviceDictionaryTable.objects.all()]


class DeviceKVStore(ExtendedKVStore):
    kvstore = get_kvstore('db://lava_scheduler_app_devicedictionarytable')


class PipelineKVStore(ExtendedKVStore):
    """
    Set a different backend table
    """
    kvstore = get_kvstore('db://lava_scheduler_app_pipelinestore')


class DeviceDictionary(DeviceKVStore):
    """
    KeyValue store for Pipeline device support
    Not a RestricedResource - may need a new class based on kvmodels
    """
    hostname = kvmodels.Field(pk=True)
    parameters = kvmodels.Field()

    class Meta:
        app_label = 'pipeline'


class Device(RestrictedResource):
    """
    A device that we can run tests on.
    """

    OFFLINE = 0
    IDLE = 1
    RUNNING = 2
    OFFLINING = 3
    RETIRED = 4
    RESERVED = 5

    STATUS_CHOICES = (
        (OFFLINE, 'Offline'),
        (IDLE, 'Idle'),
        (RUNNING, 'Running'),
        (OFFLINING, 'Going offline'),
        (RETIRED, 'Retired'),
        (RESERVED, 'Reserved')
    )

    # A device health shows a device is ready to test or not
    HEALTH_UNKNOWN, HEALTH_PASS, HEALTH_FAIL, HEALTH_LOOPING = range(4)
    HEALTH_CHOICES = (
        (HEALTH_UNKNOWN, 'Unknown'),
        (HEALTH_PASS, 'Pass'),
        (HEALTH_FAIL, 'Fail'),
        (HEALTH_LOOPING, 'Looping'),
    )

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
        User, related_name='physical-owner',
        null=True,
        blank=True,
        default=None,
        verbose_name=_(u"User with physical access")
    )

    physical_group = models.ForeignKey(
        Group, related_name='physical-group',
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

    current_job = models.ForeignKey(
        "TestJob", blank=True, unique=True, null=True, related_name='+',
        on_delete=models.SET_NULL)

    tags = models.ManyToManyField(Tag, blank=True)

    status = models.IntegerField(
        choices=STATUS_CHOICES,
        default=IDLE,
        verbose_name=_(u"Device status"),
    )

    health_status = models.IntegerField(
        choices=HEALTH_CHOICES,
        default=HEALTH_UNKNOWN,
        verbose_name=_(u"Device Health"),
    )

    last_health_report_job = models.ForeignKey(
        "TestJob", blank=True, unique=True, null=True, related_name='+',
        on_delete=models.SET_NULL)

    worker_host = models.ForeignKey(
        Worker,
        verbose_name=_(u"Worker Host"),
        null=True,
        blank=True,
        default=None
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

    def __unicode__(self):
        r = self.hostname
        r += " (%s, health %s)" % (self.get_status_display(),
                                   self.get_health_status_display())
        return r

    @models.permalink
    def get_absolute_url(self):
        return ("lava.scheduler.device.detail", [self.pk])

    @models.permalink
    def get_device_health_url(self):
        return ("lava.scheduler.labhealth.detail", [self.pk])

    def get_description(self):
        return mark_safe(self.description)

    def recent_jobs(self):
        return TestJob.objects.select_related(
            "actual_device",
            "requested_device",
            "requested_device_type",
            "submitter",
            "user",
            "group",
        ).filter(
            actual_device=self
        ).order_by(
            '-submit_time'
        )

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
            if len(self.device_type.devices_visible_to(user)) == 0:
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

    def can_submit(self, user):
        if self.status == Device.RETIRED:
            return False
        if self.is_public:
            return True
        if user.username == "lava-health":
            return True
        return self.is_owned_by(user)

    def state_transition_to(self, new_status, user=None, message=None, job=None):
        DeviceStateTransition.objects.create(
            created_by=user, device=self, old_state=self.status,
            new_state=new_status, message=message, job=job).save()
        self.status = new_status
        self.save()

    def put_into_maintenance_mode(self, user, reason, notify=None):
        if self.status in [self.RESERVED, self.OFFLINING]:
            new_status = self.OFFLINING
        elif self.status == self.RUNNING:
            if notify:
                # only one admin will be emailed when admin_notification is set.
                self.current_job.admin_notifications = notify
                self.current_job.save()
            new_status = self.OFFLINING
        else:
            new_status = self.OFFLINE
        if self.health_status == Device.HEALTH_LOOPING:
            self.health_status = Device.HEALTH_UNKNOWN
        self.state_transition_to(new_status, user=user, message=reason)

    def put_into_online_mode(self, user, reason, skiphealthcheck=False):
        if self.status == Device.OFFLINING:
            new_status = self.RUNNING
        else:
            new_status = self.IDLE

        if not skiphealthcheck:
            self.health_status = Device.HEALTH_UNKNOWN

        self.state_transition_to(new_status, user=user, message=reason)

    def put_into_looping_mode(self, user, reason):
        if self.status not in [Device.OFFLINE, Device.OFFLINING]:
            return

        self.health_status = Device.HEALTH_LOOPING

        self.state_transition_to(self.IDLE, user=user, message=reason)

    def cancel_reserved_status(self, user, reason):
        if self.status != Device.RESERVED:
            return

        self.state_transition_to(self.IDLE, user=user, message=reason)

    def too_long_since_last_heartbeat(self):
        """This is same as worker heartbeat.
        """
        if self.worker_host:
            return self.worker_host.too_long_since_last_heartbeat()
        else:
            return True

    def get_existing_health_check_job(self):
        """Get the existing health check job.
        """
        try:
            return TestJob.objects.filter((models.Q(actual_device=self) |
                                           models.Q(requested_device=self)),
                                          status__in=[TestJob.SUBMITTED,
                                                      TestJob.RUNNING],
                                          health_check=True)[0]
        except IndexError:
            return None

    def initiate_health_check_job(self):
        if self.status in [self.RETIRED]:
            return None

        existing_health_check_job = self.get_existing_health_check_job()
        if existing_health_check_job:
            return existing_health_check_job

        job_json = self.device_type.health_check_job
        if not job_json:
            # This should never happen, it's a logic error.
            self.put_into_maintenance_mode(
                None, "no job_json in initiate_health_check_job")
            raise JSONDataError("no job_json found for %r", self.hostname)
        else:
            user = User.objects.get(username='lava-health')
            job_data = simplejson.loads(job_json)
            job_data['target'] = self.hostname
            job_data['health-check'] = True
            job_json = simplejson.dumps(job_data)
            try:
                return TestJob.from_json_and_user(job_json, user, True)
            except (JSONDataError, ValueError) as e:
                self.put_into_maintenance_mode(
                    None, "Job submission failed for health job for %s: %s" % (self, e))
                raise JSONDataError("Health check job submission failed for %s: %s" % (self, e))

    def load_device_configuration(self, job_ctx=None):
        """
        Maps the DeviceDictionary to the static templates in /etc/.
        Use lava-server manage device-dictionary --import <FILE>
        to update the DeviceDictionary.
        raise: this function can raise IOError, jinja2.TemplateError or yaml.YAMLError -
            handling these exceptions may be context-dependent, users will need
            useful messages based on these exceptions.
        """
        if self.is_pipeline is False:
            return None

        # The job_ctx should not be None while an empty dict is ok
        if job_ctx is None:
            job_ctx = {}

        element = DeviceDictionary.get(self.hostname)
        # TODO: hardcoded path (determined by setup.py)
        path = utils.jinja_template_path()
        if element is None:
            return None
        data = utils.devicedictionary_to_jinja2(
            element.parameters,
            element.parameters['extends']
        )
        string_loader = jinja2.DictLoader({'%s.yaml' % self.hostname: data})
        type_loader = jinja2.FileSystemLoader([
            os.path.join(path, 'device-types')])
        env = jinja2.Environment(
            loader=jinja2.ChoiceLoader([string_loader, type_loader]),
            trim_blocks=True)
        template = env.get_template("%s.yaml" % self.hostname)

        return yaml.load(template.render(**job_ctx))

    @property
    def is_exclusive(self):
        exclusive = False
        # check the device dictionary if this is exclusively a pipeline device
        device_dict = DeviceDictionary.get(self.hostname)
        if device_dict:
            device_dict = device_dict.to_dict()
            if 'parameters' not in device_dict or device_dict['parameters'] is None:
                return exclusive
            if 'exclusive' in device_dict['parameters'] and device_dict['parameters']['exclusive'] == 'True':
                exclusive = True
        return exclusive


class TemporaryDevice(Device):
    """
    A temporary device which inherits all properties of a normal Device.
    Heavily used by vm-groups implementation.

    This uses "Multi-table inheritance" of django models, since we need a
    separate table to maintain the temporary devices.
    See: https://docs.djangoproject.com/en/dev/topics/db/models/#multi-table-inheritance
    """
    vm_group = models.CharField(
        verbose_name=_(u"VM Group"),
        blank=True,
        max_length=64,
        null=True,
        default=None
    )

    class Meta:
        pass


class JobFailureTag(models.Model):
    """
    Allows us to maintain a set of common ways jobs fail. These can then be
    associated with a TestJob so we can do easy data mining
    """
    name = models.CharField(unique=True, max_length=256)

    description = models.TextField(null=True, blank=True)

    def __unicode__(self):
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
    if type(tags) != list:
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
    q = q.__and__(~models.Q(status=Device.RETIRED))
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


def _check_exclusivity(device_list, pipeline=True):
    """
    Checks whether the device is exclusive to the pipeline.
    :param device_list: A list of device objects to check
    :param pipeline: whether the job being checked is a pipeline job
    :return: a subset of the device_list to which the job can be submitted.
    """
    allow = []
    check_type = "YAML" if pipeline else "JSON"
    if len(device_list) == 0:
        # logic error
        return allow
    for device in device_list:
        if pipeline and not device.is_pipeline:
            continue
        if not pipeline and device.is_exclusive:
            # devices which are exclusive to the pipeline cannot accept non-pipeline jobs.
            continue
        allow.append(device)
    if len(allow) == 0:
        raise DevicesUnavailableException(
            "No devices of the requested type are currently available for %s submissions" % check_type)
    return allow


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
    if type(device_list) != list or len(device_list) == 0:
        # logic error
        return allow
    device_type = None
    for device in device_list:
        device_type = device.device_type
        if device.status != Device.RETIRED and device.can_submit(user):
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
    if len(device_type.devices_visible_to(user)) == 0:
        msg = "Device type '%s' is unavailable to user '%s'" % (name, user.username)
        logger.error(msg)
        raise DevicesUnavailableException(msg)
    return device_type


def _check_device_types(user):
    """
    Filters the list of device types to exclude types which are
    owner_only if the user is not an owner of one of those devices.
    :param user: the user submitting the TestJob
    """

    # Get all device types that are available for scheduling.
    device_types = DeviceType.objects.values_list('name').filter(
        models.Q(device__status=Device.IDLE) |
        models.Q(device__status=Device.RUNNING) |
        models.Q(device__status=Device.RESERVED) |
        models.Q(device__status=Device.OFFLINE) |
        models.Q(device__status=Device.OFFLINING))\
        .annotate(num_count=models.Count('name')).order_by('name')

    # Count each of the device types available.
    # reduce the count by the number of devices available to that user
    # if this type is hidden  Skip if this results in zero devices of that type.
    all_devices = {}
    for dt in device_types:
        # dt[0] -> device type name
        # dt[1] -> device type count
        device_type = DeviceType.objects.get(name=dt[0])
        if device_type.owners_only:
            count = len(device_type.devices_visible_to(user))
            if count > 0:
                all_devices[dt[0]] = count
        if dt[1] > 0:
            all_devices[dt[0]] = dt[1]
    return all_devices


def _create_pipeline_job(job_data, user, taglist, device=None, device_type=None, target_group=None, orig=None):

    if type(job_data) is not dict:
        # programming error
        raise RuntimeError("Invalid job data %s" % job_data)

    if 'connection' in job_data:
        device_type = None
    elif not device and not device_type:
        # programming error
        return None

    if not taglist:
        taglist = []

    if not orig:
        orig = yaml.dump(job_data)
    job = TestJob(definition=orig, original_definition=orig,
                  submitter=user,
                  requested_device=device,
                  requested_device_type=device_type,
                  target_group=target_group,
                  description=job_data['job_name'],
                  health_check=False,
                  user=user, is_public=True,
                  is_pipeline=True)
    job.save()
    # need a valid job before the tags can be assigned, then it needs to be saved again.
    for tag in Tag.objects.filter(name__in=taglist):
        job.tags.add(tag)

    # add pipeline to jobpipeline, update with results later - needs the job.id.
    dupe = JobPipeline.get(job.id)
    if dupe:
        # this should be impossible
        # FIXME: needs a unit test
        raise RuntimeError("Duplicate job id?")
    store = JobPipeline(job_id=job.id)
    store.pipeline = {}
    store.save()
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

    Actual device assignment happens in lava_scheduler_daemon:dbjobsource.py until
    this migrates into dispatcher-master.

    params:
      job_data - dictionary of the submission YAML
      user: the user submitting the job
    returns:
      list of all jobs created using the specified type(s) which meet the protocol criteria,
      specified device tags and which the user is able to submit.
    exceptions:
        DevicesUnavailableException if all criteria cannot be met.
    """
    device_list = []
    if type(job_data) is dict and 'protocols' not in job_data:
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
                device_list = Device.objects.filter(device_type=device_type, is_pipeline=True)
                for device in device_list:
                    if _check_submit_to_device([device], user):
                        allowed_devices.append(device)

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


class PipelineStore(models.Model):
    kee = models.CharField(max_length=255)
    value = models.TextField()

    def lookup_job_pipeline(self):
        """
        Exports the pipeline as YAML
        """
        # FIXME: add a command line call to retrieve specific items - too slow to show in admin interface.
        val = self.kee
        msg = val.replace('__KV_STORE_::lava_scheduler_app.models.JobPipeline:', '')
        data = JobPipeline.get(msg)
        if type(data.pipeline) == str:
            # if this fails, fix lava_dispatcher.pipeline.actions.explode()
            data.pipeline = yaml.load(data.pipeline)
        return data


class JobPipeline(PipelineKVStore):
    """
    KeyValue store for Pipeline device support
    Not a RestricedResource - may need a new class based on kvmodels
    """
    job_id = kvmodels.Field(pk=True)
    pipeline = kvmodels.Field()

    class Meta:
        app_label = 'pipeline'


class TestJob(RestrictedResource):
    """
    A test job is a test process that will be run on a Device.
    """

    SUBMITTED = 0
    RUNNING = 1
    COMPLETE = 2
    INCOMPLETE = 3
    CANCELED = 4
    CANCELING = 5

    STATUS_CHOICES = (
        (SUBMITTED, 'Submitted'),
        (RUNNING, 'Running'),
        (COMPLETE, 'Complete'),
        (INCOMPLETE, 'Incomplete'),
        (CANCELED, 'Canceled'),
        (CANCELING, 'Canceling'),
    )

    LOW = 0
    MEDIUM = 50
    HIGH = 100

    PRIORITY_CHOICES = (
        (LOW, 'Low'),
        (MEDIUM, 'Medium'),
        (HIGH, 'High'),
    )

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

    vm_group = models.CharField(
        verbose_name=_(u"VM Group"),
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

    submit_token = models.ForeignKey(
        AuthToken, null=True, blank=True, on_delete=models.SET_NULL)

    description = models.CharField(
        verbose_name=_(u"Description"),
        max_length=200,
        null=True,
        blank=True,
        default=None
    )

    health_check = models.BooleanField(default=False)

    # Only one of requested_device, requested_device_type or dynamic_connection
    # should be non-null. requested_device is not supported for pipeline jobs,
    # except health checks. Dynamic connections have no device.
    requested_device = models.ForeignKey(
        Device, null=True, default=None, related_name='+', blank=True)
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
        Device, null=True, default=None, related_name='+', blank=True)

    submit_time = models.DateTimeField(
        verbose_name=_(u"Submit time"),
        auto_now=False,
        auto_now_add=True
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
        if self.end_time is None:
            return None
        return self.end_time - self.start_time

    status = models.IntegerField(
        choices=STATUS_CHOICES,
        default=SUBMITTED,
        verbose_name=_(u"Status"),
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

    vmgroup_definition = models.TextField(
        editable=False,
        blank=True
    )

    is_pipeline = models.BooleanField(
        verbose_name="Pipeline job?",
        default=False,
        editable=False
    )

    # only one value can be set as there is only one opportunity
    # to transition a device from Running to Offlining.
    admin_notifications = models.TextField(
        editable=False,
        blank=True
    )

    log_file = models.FileField(
        upload_to='lava-logs', default=None, null=True, blank=True)

    @property
    def size_limit(self):
        return settings.LOG_SIZE_LIMIT * 1024 * 1024

    @property
    def output_dir(self):
        return os.path.join(settings.MEDIA_ROOT, 'job-output', 'job-%s' % self.id)

    def output_file(self):
        output_path = os.path.join(self.output_dir, 'output.txt')
        if os.path.exists(output_path):
            return open(output_path, encoding='utf-8', errors='replace')
        elif self.log_file:
            log_file = self.log_file
            if log_file:
                try:
                    open(log_file.name)
                except IOError:
                    log_file = None
            return log_file
        else:
            return None

    def archived_job_file(self):
        """Checks if the current job's log output file was archived.
        """
        last_info = os.path.join(settings.ARCHIVE_ROOT, 'job-output',
                                 'last.info')

        if os.path.exists(last_info):
            with open(last_info, 'r') as last:
                last_archived_job = int(last.read())
                last.close()

            if self.id <= last_archived_job:
                return True
            else:
                return False

        return False

    def archived_bundle(self):
        """Checks if the current bundle file was archived.
        """
        last_info = os.path.join(settings.ARCHIVE_ROOT, 'bundles', 'last.info')

        if os.path.exists(last_info):
            with open(last_info, 'r') as last:
                last_archived_bundle = int(last.read())
                last.close()

            if self.id <= last_archived_bundle:
                return True
            else:
                return False

        return False

    failure_tags = models.ManyToManyField(
        JobFailureTag, blank=True, related_name='failure_tags')
    failure_comment = models.TextField(null=True, blank=True)

    _results_link = models.CharField(
        max_length=400, default=None, null=True, blank=True, db_column="results_link")

    _results_bundle = models.OneToOneField(
        Bundle, null=True, blank=True, db_column="results_bundle_id",
        on_delete=models.SET_NULL)

    @property
    def results_link(self):
        if self._results_bundle:
            return self._results_bundle.get_permalink()
        elif self._results_link:
            return self._results_link
        elif self.is_pipeline:
            return u'/results/%s' % self.id
        else:
            return None

    @property
    def device_role(self):
        if not (self.is_multinode or self.is_vmgroup):
            return "Error"
        if self.is_pipeline:
            data = yaml.load(self.definition)
            if 'protocols' not in data:
                return 'Error'
            if 'lava-multinode' not in data['protocols']:
                return 'Error'
            if 'role' not in data['protocols']['lava-multinode']:
                return 'Error'
            return data['protocols']['lava-multinode']['role']
        json_data = simplejson.loads(self.definition)
        if 'role' not in json_data:
            return "Error"
        return json_data['role']

    @property
    def results_bundle(self):
        if self._results_bundle:
            return self._results_bundle
        if not self.results_link:
            return None
        sha1 = self.results_link.strip('/').split('/')[-1]
        try:
            return Bundle.objects.get(content_sha1=sha1)
        except Bundle.DoesNotExist:
            return None

    def __unicode__(self):
        job_type = self.health_check and 'health check' or 'test'
        r = "%s %s job" % (self.get_status_display(), job_type)
        if self.actual_device:
            r += " on %s" % (self.actual_device.hostname)
        else:
            if self.requested_device:
                r += " for %s" % (self.requested_device.hostname)
            if self.requested_device_type:
                r += " for %s" % (self.requested_device_type.name)
        r += " (%d)" % (self.id)
        return r

    @models.permalink
    def get_absolute_url(self):
        return ("lava.scheduler.job.detail", [self.display_id])

    @classmethod
    def from_yaml_and_user(cls, yaml_data, user):
        """
        Runs the submission checks on incoming pipeline jobs.
        Either rejects the job with a DevicesUnavailableException (which the caller is expected to handle), or
        creates a TestJob object for the submission and saves that testjob into the database.
        This function must *never* be involved in setting the state of this job or the state of any associated device.
        'target' is not supported, so requested_device is always None at submission time.
        Retains yaml_data as the original definition to retain comments.
        """
        job_data = yaml.load(yaml_data)

        # pipeline protocol handling, e.g. lava-multinode
        job_list = _pipeline_protocols(job_data, user, yaml_data)
        if job_list:
            return job_list

        device_type = _get_device_type(user, job_data['device_type'])
        allow = _check_submit_to_device(list(Device.objects.filter(
            device_type=device_type, is_pipeline=True)), user)
        if not allow:
            raise DevicesUnavailableException("No devices of type %s have pipeline support." % device_type)
        taglist = _get_tag_list(job_data.get('tags', []), True)
        if taglist:
            supported = _check_tags(taglist, device_type=device_type)
            _check_tags_support(supported, allow)

        return _create_pipeline_job(job_data, user, taglist, device=None, device_type=device_type, orig=yaml_data)

    @classmethod
    def from_json_and_user(cls, json_data, user, health_check=False):
        """
        Constructs one or more TestJob objects from a JSON data and a submitting
        user. Handles multinode jobs and creates one job for each target
        device.

        For single node jobs, returns the job object created. For multinode
        jobs, returns an array of test objects.
        """
        job_data = simplejson.loads(json_data)
        validate_job_data(job_data)
        logger = logging.getLogger('lava_scheduler_app')

        # Validate job, for parameters, specific to multinode that has been
        # input by the user. These parameters are reserved by LAVA and
        # generated during job submissions.
        reserved_job_params = ["group_size", "role", "sub_id", "target_group"]
        reserved_params_found = set(reserved_job_params).intersection(
            set(job_data.keys()))
        if reserved_params_found:
            raise JSONDataError("Reserved parameters found in job data %s" %
                                str([x for x in reserved_params_found]))

        taglist = _get_tag_list(job_data.get('tags', []))

        if 'target' in job_data:
            if 'device_type' in job_data:
                del job_data['device_type']
            device_type = None
            try:
                target = Device.objects.filter(
                    ~models.Q(status=Device.RETIRED))\
                    .get(hostname=job_data['target'])
            except Device.DoesNotExist:
                logger.debug("Requested device %s is unavailable." % job_data['target'])
                raise DevicesUnavailableException(
                    "Requested device %s is unavailable." % job_data['target'])
            _check_exclusivity([target], False)
            _check_submit_to_device([target], user)
            _check_tags_support(_check_tags(taglist, hostname=target), _check_submit_to_device([target], user))
        elif 'device_type' in job_data:
            target = None
            device_type = _get_device_type(user, job_data['device_type'])
            allow = _check_submit_to_device(list(Device.objects.filter(
                device_type=device_type)), user)
            allow = _check_exclusivity(allow, False)
            _check_tags_support(_check_tags(taglist, device_type=device_type), allow)
        elif 'device_group' in job_data:
            target = None
            device_type = None
            requested_devices = {}

            # Check if the requested devices are available for job run.
            for device_group in job_data['device_group']:
                device_type = _get_device_type(user, device_group['device_type'])
                count = device_group['count']
                taglist = _get_tag_list(device_group.get('tags', []))
                allow = _check_submit_to_device(list(Device.objects.filter(
                    device_type=device_type)), user)
                allow = _check_exclusivity(allow, False)
                _check_tags_support(_check_tags(taglist, device_type=device_type), allow)
                if device_type in requested_devices:
                    requested_devices[device_type] += count
                else:
                    requested_devices[device_type] = count

            all_devices = _check_device_types(user)
            for board, count in requested_devices.iteritems():
                if all_devices.get(board.name, None) and \
                        count <= all_devices[board.name]:
                    continue
                else:
                    raise DevicesUnavailableException(
                        "Requested %d %s device(s) - only %d available." %
                        (count, board, all_devices.get(board.name, 0)))
        elif 'vm_group' in job_data:
            target = None
            device_type = None
            requested_devices = {}
            vm_group = job_data['vm_group']

            # Check if the requested device is available for job run.
            try:
                device_type = DeviceType.objects.get(
                    name=vm_group['host']['device_type'])
            except Device.DoesNotExist as e:
                raise DevicesUnavailableException(
                    "Device type '%s' is unavailable. %s" %
                    (vm_group['host']['device_type'], e))
            role = vm_group['host'].get('role', None)
            allow = _check_submit_to_device(
                list(Device.objects.filter(device_type=device_type)), user)
            _check_exclusivity(allow, False)
            requested_devices[device_type.name] = (1, role)

            # Validate and get the list of vms requested. These are dynamic vms
            # that will be created by the above vm_group host, so we need not
            # bother about whether this vm device exists at this point of time
            # (they won't since they will be created dynamically).
            vms_list = vm_group['vms']
            for vm in vms_list:
                dtype = vm['device_type']
                count = vm.get('count', 1)
                role = vm.get('role', None)
                # Right now we support only 'kvm' type vms.
                #
                # FIXME: Once we have support for 'xen' augment this list
                if dtype in ['kvm', 'kvm-arm', 'kvm-aarch64']:
                    if dtype in requested_devices:
                        count = count + requested_devices[dtype][0]
                        requested_devices[dtype] = (count, role)
                    else:
                        requested_devices[dtype] = (count, role)
                else:
                    raise DevicesUnavailableException(
                        "Device type '%s' is not a supported VMs type" %
                        dtype)
        else:
            raise JSONDataError(
                "No 'target' or 'device_type', 'device_group' or 'vm_group' "
                "are found in job data.")

        priorities = dict([(j.upper(), i) for i, j in cls.PRIORITY_CHOICES])
        priority = cls.MEDIUM
        if 'priority' in job_data:
            priority_key = job_data['priority'].upper()
            if priority_key not in priorities:
                raise JSONDataError("Invalid job priority: %r" % priority_key)
            priority = priorities[priority_key]

        for email_field in 'notify', 'notify_on_incomplete':
            if email_field in job_data:
                value = job_data[email_field]
                msg = ("%r must be a list of email addresses if present"
                       % email_field)
                if not isinstance(value, list):
                    raise ValueError(msg)
                for address in value:
                    if not isinstance(address, basestring):
                        raise ValueError(msg)
                    try:
                        validate_email(address)
                    except ValidationError:
                        raise ValueError(
                            "%r is not a valid email address." % address)

        if job_data.get('health_check', False) and not health_check:
            raise ValueError(
                "cannot submit a job with health_check: true via the api.")

        job_name = job_data.get('job_name', '')

        submitter = user
        group = None
        is_public = True

        for action in job_data['actions']:
            if not action['command'].startswith('submit_results'):
                continue
            stream = action['parameters']['stream']
            try:
                bundle_stream = BundleStream.objects.get(pathname=stream)
            except BundleStream.DoesNotExist:
                raise ValueError("stream %s not found" % stream)
            if not bundle_stream.can_upload(submitter):
                raise ValueError(
                    "you cannot submit to the stream %s" % stream)
            # NOTE: this *overwrites* the HTTP:Request.user with the BundleStream.user
            # use the cached submitter value for user checks.
            if not bundle_stream.is_anonymous:
                user, group, is_public = (bundle_stream.user,
                                          bundle_stream.group,
                                          bundle_stream.is_public)
            server = action['parameters']['server']
            parsed_server = urlparse.urlsplit(server)
            action["parameters"]["server"] = utils.rewrite_hostname(server)
            if parsed_server.hostname is None:
                raise ValueError("invalid server: %s" % server)

        # hidden device types must have a private stream
        # we need to have already prevented other users from
        # seeing this device_type before getting to this point.
        check_type = target.device_type if target else device_type
        if isinstance(check_type, unicode):
            check_type = DeviceType.objects.get(name=check_type)
        if check_type.owners_only and is_public:
            raise DevicesUnavailableException(
                "%s is a hidden device type and must have a private bundle stream" %
                check_type)

        # MultiNode processing - tally allowed devices with the
        # device_types requested per role.
        allowed_devices = {}
        orig_job_data = job_data
        job_data = utils.process_repeat_parameter(job_data)
        if 'device_group' in job_data:
            device_count = {}
            target = None  # prevent multinode jobs reserving devices which are currently running.
            for clients in job_data["device_group"]:
                device_type = str(clients['device_type'])
                if device_type not in allowed_devices:
                    allowed_devices[device_type] = []
                count = int(clients["count"])
                if device_type not in device_count:
                    device_count[device_type] = 0
                device_count[device_type] += count

                device_list = Device.objects.filter(device_type=device_type)
                for device in device_list:
                    if device.can_submit(submitter):
                        allowed_devices[device_type].append(device)
                if len(allowed_devices[device_type]) < device_count[device_type]:
                    raise DevicesUnavailableException("Not enough devices of type %s are currently "
                                                      "available to user %s"
                                                      % (device_type, submitter))

            target_group = str(uuid.uuid4())
            node_json = utils.split_multi_job(job_data, target_group)
            job_list = []
            try:
                parent_id = (TestJob.objects.latest('id')).id + 1
            except:
                parent_id = 1
            child_id = 0

            for role in node_json:
                role_count = len(node_json[role])
                for c in range(0, role_count):
                    device_type = DeviceType.objects.get(
                        name=node_json[role][c]["device_type"])
                    sub_id = '.'.join([str(parent_id), str(child_id)])

                    # Add sub_id to the generated job dictionary.
                    node_json[role][c]["sub_id"] = sub_id

                    job = TestJob(
                        sub_id=sub_id, submitter=submitter,
                        requested_device=target,
                        description=job_name,
                        requested_device_type=device_type,
                        definition=simplejson.dumps(node_json[role][c],
                                                    sort_keys=True,
                                                    indent=4 * ' '),
                        original_definition=simplejson.dumps(json_data,
                                                             sort_keys=True,
                                                             indent=4 * ' '),
                        multinode_definition=json_data,
                        health_check=health_check, user=user, group=group,
                        is_public=is_public,
                        priority=TestJob.MEDIUM,  # multinode jobs have fixed priority
                        target_group=target_group)
                    job.save()

                    # Add tags as defined per role for each job.
                    taglist = _get_tag_list(node_json[role][c].get("tags", []))
                    if taglist:
                        for tag in Tag.objects.filter(name__in=taglist):
                            job.tags.add(tag)
                    # This save is important though we have one few lines
                    # above, because, in order to add to the tags table we need
                    # a foreign key reference from the jobs table which happens
                    # with the previous job.save(). The following job.save()
                    # ensures the tags are saved properly with references.
                    job.save()
                    job_list.append(job)
                    child_id += 1
            return job_list

        elif 'vm_group' in job_data:
            target = None
            vm_group = str(uuid.uuid4())
            node_json = utils.split_vm_job(job_data, vm_group)
            job_list = []
            try:
                parent_id = (TestJob.objects.latest('id')).id + 1
            except:
                parent_id = 1
            child_id = 0

            for role in node_json:
                role_count = len(node_json[role])
                for c in range(0, role_count):
                    name = node_json[role][c]["device_type"]
                    try:
                        device_type = DeviceType.objects.get(name=name)
                    except DeviceType.DoesNotExist as e:
                        if name != "dynamic-vm":
                            raise DevicesUnavailableException("device type %s does not exist" % name)
                        else:
                            device_type = DeviceType.objects.create(name="dynamic-vm")
                    sub_id = '.'.join([str(parent_id), str(child_id)])

                    is_vmhost = False
                    if 'is_vmhost' in node_json[role][c]:
                        is_vmhost = node_json[role][c]['is_vmhost']
                    if not is_vmhost:
                        description = "tmp device for %s vm-group" % vm_group
                        node_json[role][c]["target"] = '%s-job%s' % \
                            (node_json[role][c]['target'], sub_id)
                        target = TemporaryDevice(
                            hostname=node_json[role][c]["target"], is_public=True,
                            device_type=device_type, description=description,
                            worker_host=None, vm_group=vm_group)
                        target.save()

                    # Add sub_id to the generated job dictionary.
                    node_json[role][c]["sub_id"] = sub_id

                    job = TestJob(
                        sub_id=sub_id, submitter=submitter,
                        requested_device=target,
                        description=job_name,
                        requested_device_type=device_type,
                        definition=simplejson.dumps(node_json[role][c],
                                                    sort_keys=True,
                                                    indent=4 * ' '),
                        original_definition=simplejson.dumps(json_data,
                                                             sort_keys=True,
                                                             indent=4 * ' '),
                        vmgroup_definition=json_data,
                        health_check=health_check, user=user, group=group,
                        is_public=is_public,
                        priority=TestJob.MEDIUM,  # vm_group jobs have fixed priority
                        vm_group=vm_group)
                    job.save()
                    job_list.append(job)
                    child_id += 1

                    # Reset values if already set
                    device_type = None
                    target = None
            return job_list

        else:
            job_data = simplejson.dumps(job_data, sort_keys=True,
                                        indent=4 * ' ')
            orig_job_data = simplejson.dumps(orig_job_data, sort_keys=True,
                                             indent=4 * ' ')
            job = TestJob(
                definition=job_data, original_definition=orig_job_data,
                submitter=submitter, requested_device=target,
                requested_device_type=device_type, description=job_name,
                health_check=health_check, user=user, group=group,
                is_public=is_public, priority=priority)
            job.save()
            for tag in Tag.objects.filter(name__in=taglist):
                job.tags.add(tag)
            return job

    def _can_admin(self, user):
        """ used to check for things like if the user can cancel or annotate
        a job failure
        """
        owner = False
        if self.actual_device is not None:
            owner = self.actual_device.can_admin(user)
        return (user.is_superuser or user == self.submitter or owner or
                user.has_perm('lava_scheduler_app.cancel_resubmit_testjob'))

    def can_change_priority(self, user):
        """
        Permission and state required to change job priority.
        Multinode jobs cannot have their priority changed.
        """
        return self._can_admin(user) and self.status == TestJob.SUBMITTED and not self.is_multinode

    def can_annotate(self, user):
        """
        Permission required for user to add failure information to a job
        """
        states = [TestJob.COMPLETE, TestJob.INCOMPLETE, TestJob.CANCELED]
        return self._can_admin(user) and self.status in states

    def can_cancel(self, user):
        return self._can_admin(user) and self.status <= TestJob.RUNNING

    def can_resubmit(self, user):
        if self.is_pipeline:
            # FIXME: allow resubmission once UI submission of YAML is also supported.
            return False
        return (user.is_superuser or
                user.has_perm('lava_scheduler_app.cancel_resubmit_testjob'))

    def cancel(self, user=None):
        """
        Sets the Canceling status and clears reserved status, if any.
        Actual job cancellation (ending the lava-dispatch process)
        is done by the scheduler daemon (or lava-slave).
        :param user: user requesting the cancellation, or None.
        """
        logger = logging.getLogger('lava_scheduler_app')
        if not user:
            logger.info("Unidentified user requested cancellation of job submitted by %s" % (
                self.submitter
            ))
            user = self.submitter
        # if SUBMITTED with actual_device - clear the actual_device back to idle.
        if self.status == TestJob.SUBMITTED and self.actual_device is not None:
            logger.info("Cancel %s - clearing reserved status for device %s" % (
                self, self.actual_device.hostname))
            self.actual_device.cancel_reserved_status(user, "job-cancel")
            self.status = TestJob.CANCELING
            self._send_cancellation_mail(user)
        elif self.status == TestJob.SUBMITTED:
            logger.info("Cancel %s" % self)
            self.status = TestJob.CANCELED
            self._send_cancellation_mail(user)
        elif self.status == TestJob.RUNNING:
            logger.info("Cancel %s" % self)
            self.status = TestJob.CANCELING
            self._send_cancellation_mail(user)
        elif self.status == TestJob.CANCELING:
            logger.info("Completing cancel of %s" % self)
            self.status = TestJob.CANCELED
        if user:
            self.failure_comment = "Canceled by %s" % user.username
        self.save()

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
        if self.status != self.COMPLETE:
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

    @property
    def sub_jobs_list(self):
        if self.is_multinode:
            jobs = TestJob.objects.filter(
                target_group=self.target_group).order_by('id')
            return jobs
        elif self.is_vmgroup:
            jobs = TestJob.objects.filter(
                vm_group=self.vm_group).order_by('id')
            return jobs
        else:
            return None

    @property
    def is_multinode(self):
        if self.target_group:
            return True
        else:
            return False

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
    def is_vmgroup(self):
        if self.is_pipeline:
            return False
        if self.vm_group:
            return True
        else:
            return False

    @property
    def display_id(self):
        if self.sub_id:
            return self.sub_id
        else:
            return self.id

    @classmethod
    def get_by_job_number(cls, job_id):
        """If JOB_ID is of the form x.y ie., a multinode job notation, then
        query the database with sub_id and get the JOB object else use the
        given id as the primary key value.

        Returns JOB object.
        """
        if '.' in str(job_id):
            job = get_object_or_404(TestJob.objects, sub_id=job_id)
        else:
            job = get_object_or_404(TestJob.objects, pk=job_id)
        return job

    @property
    def display_definition(self):
        """If ORIGINAL_DEFINITION is stored in the database return it, for jobs
        which do not have ORIGINAL_DEFINITION ie., jobs that were submitted
        before this attribute was introduced, return the DEFINITION.
        """
        if self.original_definition and\
                not (self.is_multinode or self.is_vmgroup):
            return self.original_definition
        else:
            return self.definition

    @property
    def is_ready_to_start(self):  # FIXME for secondary connections
        def device_ready(job):
            """
            job.actual_device is not None is insufficient.
            The device also needs to be reserved and not have
            a different job set in device.current_job.
            The device and the job update in different transactions, so, the following
            *must* be allowed:
              job.status in [SUBMITTED, RUNNING] and job.actual_device.status in [RESERVED, RUNNING]
              *only as long as* if job.actual_device.current_job:
                job == job.actual_device.current_job
            :param device: the actual device for this job, or None
            :return: True if there is a device and that device is status Reserved
            """
            logger = logging.getLogger('lava_scheduler_app')
            if not job.actual_device:
                return False
            if job.actual_device.current_job and job.actual_device.current_job != job:
                logger.debug(
                    "%s current_job %s differs from job being checked: %s",
                    job.actual_device, job.actual_device.current_job, job)
                return False
            if job.actual_device.status not in [Device.RESERVED, Device.RUNNING]:
                logger.debug("%s is not ready to start a job", job.actual_device)
                return False
            return True

        def ready(job):
            return job.status == TestJob.SUBMITTED and device_ready(job)

        def ready_or_running(job):
            return job.status in [TestJob.SUBMITTED, TestJob.RUNNING] and device_ready(job)

        if self.is_multinode or self.is_vmgroup:
            return ready_or_running(self) and all(map(ready_or_running, self.sub_jobs_list))
        else:
            return ready(self)


class TestJobUser(models.Model):

    class Meta:
        unique_together = ("test_job", "user")

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


class DeviceStateTransition(models.Model):
    created_on = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    device = models.ForeignKey(Device, related_name='transitions')
    job = models.ForeignKey(TestJob, null=True, blank=True, on_delete=models.SET_NULL)
    old_state = models.IntegerField(choices=Device.STATUS_CHOICES)
    new_state = models.IntegerField(choices=Device.STATUS_CHOICES)
    message = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return u"%s: %s -> %s (%s)" % (self.device.hostname,
                                       self.get_old_state_display(),
                                       self.get_new_state_display(),
                                       self.message)

    def update_message(self, message):
        self.message = message
        self.save()
