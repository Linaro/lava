from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import ugettext as _

from linaro_django_jsonfield.models import JSONField


class DeviceType(models.Model):

    name = models.SlugField(unique=True)

    def __unicode__(self):
        return self.name

    # We will probably hang uboot command and such off here...


class Device(models.Model):
    """
    Model for supported devices (boards)
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
        max_length = 200
    )

    device_type = models.ForeignKey(
        DeviceType, verbose_name=_(u"Device type"))

    status = models.IntegerField(
        choices = STATUS_CHOICES,
        default = IDLE,
        verbose_name = _(u"Device status"),
        editable = False
    )

    def __unicode__(self):
        return self.hostname

    @classmethod
    def find_devices_by_type(cls, device_type):
        return device_type.device_set.all()


class TestJob(models.Model):
    """
    Model for test jobs
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
        editable = False
    )
    definition = JSONField(
        blank = True,
        editable = False,
        null = True
    )

    def __unicode__(self):
        return self.description

    @classmethod
    def from_json_and_user(cls, json, user):
        pass
