import json

from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import ugettext as _


class DeviceType(models.Model):
    """
    A class of device, for example a pandaboard or a snowball.
    """

    name = models.SlugField(primary_key=True)

    def __unicode__(self):
        return self.name

    # We will probably hang uboot command and such off here...


class Device(models.Model):
    """
    A device that we can run tests on.
    """

    OFFLINE = 0
    IDLE = 1
    RUNNING = 2

    STATUS_CHOICES = (
        (OFFLINE, 'Offline'),
        (IDLE, 'Idle'),
        (RUNNING, 'Running'),
    )

    hostname = models.CharField(
        verbose_name = _(u"Hostname"),
        max_length = 200,
        primary_key = True,
    )

    device_type = models.ForeignKey(
        DeviceType, verbose_name=_(u"Device type"))

    current_job = models.ForeignKey(
        "TestJob", blank=True, unique=True, null=True)

    status = models.IntegerField(
        choices = STATUS_CHOICES,
        default = IDLE,
        verbose_name = _(u"Device status"),
    )

    def __unicode__(self):
        return self.hostname

    #@classmethod
    #def find_devices_by_type(cls, device_type):
    #    return device_type.device_set.all()


class TestJob(models.Model):
    """
    A test job is a test process that will be run on a Device.
    """

    SUBMITTED = 0
    RUNNING = 1
    COMPLETE = 2
    INCOMPLETE = 3
    CANCELED = 4

    STATUS_CHOICES = (
        (SUBMITTED, 'Submitted'),
        (RUNNING, 'Running'),
        (COMPLETE, 'Complete'),
        (INCOMPLETE, 'Incomplete'),
        (CANCELED, 'Canceled'),
    )

    submitter = models.ForeignKey(
        User,
        verbose_name = _(u"Submitter"),
    )

    #description = models.CharField(
    #    verbose_name = _(u"Description"),
    #    max_length = 200
    #)

    target = models.ForeignKey(Device, null=True)
    device_type = models.ForeignKey(DeviceType)

    #priority = models.IntegerField(
    #    verbose_name = _(u"Priority"),
    #    default=0)
    submit_time = models.DateTimeField(
        verbose_name = _(u"Submit time"),
        auto_now = False,
        auto_now_add = True
    )
    start_time = models.DateTimeField(
        verbose_name = _(u"Start time"),
        auto_now = False,
        auto_now_add = False,
        null = True,
        blank = True,
        editable = False
    )
    end_time = models.DateTimeField(
        verbose_name = _(u"End time"),
        auto_now = False,
        auto_now_add = False,
        null = True,
        blank = True,
        editable = False
    )
    status = models.IntegerField(
        choices = STATUS_CHOICES,
        default = SUBMITTED,
        verbose_name = _(u"Status"),
    )
    definition = models.TextField(
        editable = False,
    )

    #def __unicode__(self):
    #    return self.description

    @classmethod
    def from_json_and_user(cls, json_data, user):
        job_data = json.loads(json_data)
        if 'target' in job_data:
            target = Device.objects.get(hostname=job_data['target'])
            device_type = target.device_type
        else:
            target = None
            device_type = DeviceType.objects.get(name=job_data['device_type'])
        job = TestJob(
            definition=json_data, submitter=user, device_type=device_type,
            target=target)
        job.save()
        return job
