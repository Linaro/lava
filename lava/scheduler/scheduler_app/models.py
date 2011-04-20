from django.db import models
from django.utils.translation import ugettext as _

from linaro_django_jsonfield.models import JSONField


class DeviceType(models.Model):

    name = models.SlugField(unique=True)

    def __unicode__(self):
        return self.name

    # We will probably hang uboot command and such off here...


class Tag(models.Model):

    name = models.SlugField(unique=True)

    def __unicode__(self):
        return self.name


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

    tags = models.ManyToManyField(Tag, blank=True)

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

    def add_tag(self, tagname):
        tag = Tag.objects.get_or_create(name=tagname)[0]
        self.tags.add(tag)


class TestSuite(models.Model):
    """
    Model representing test suites
    """
    name = models.CharField(
        verbose_name = _(u"Test suite"),
        max_length = 50
    )
    definition = JSONField(
        blank = False,
        editable = True,
        null = True
    )

    def __unicode__(self):
        return self.name


class TestCase(models.Model):
    """
    Model representing test cases
    """
    name = models.CharField(
        verbose_name = _(u"Test case"),
        max_length = 50
    )
    test_suite = models.ForeignKey(TestSuite)
    definition = JSONField(
        blank = False,
        editable = True,
        null = True
    )

    def __unicode__(self):
        return self.name


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

    submitter = models.CharField(
        verbose_name = _(u"Submitter"),
        max_length = 50
    )
    description = models.CharField(
        verbose_name = _(u"Description"),
        max_length = 200
    )

    target = models.ForeignKey(Device, null=True)
    tags = models.ManyToManyField(Tag, blank=True)
    device_type = models.ForeignKey(DeviceType)

    timeout = models.IntegerField(verbose_name = _(u"Timeout"))
    priority = models.IntegerField(
        verbose_name = _(u"Priority"),
        default=0)
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

    def available_devices(self):
        # Available machines are:
        #  1) of the required type
        #  2) idle
        #  3) have all the tags this job has.

        # XXX this ignores any target that has been set for this job

        # The nice readable version:
        #devices = Device.objects.filter(
        #    device_type=self.device_type,
        #    status=Device.IDLE)
        #for t in self.tags.all():
        #    devices = devices.filter(tags__name=t.name)
        #return devices

        # The do it all in one SQL query version:
        return Device.objects.raw(
            '''
            select * from scheduler_app_device
             where device_type_id = %s
               and status = %s
               and (select count(*) from scheduler_app_testjob_tags
                     where testjob_id = %s
                           and tag_id not in (select tag_id
                                                from scheduler_app_device_tags
                                               where device_id = device_type_id)) = 0
            ''',
            [self.device_type_id, Device.IDLE, self.id])

    def add_tag(self, tagname):
        tag = Tag.objects.get_or_create(name=tagname)[0]
        self.tags.add(tag)
