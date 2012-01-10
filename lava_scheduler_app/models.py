import simplejson

from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import ugettext as _

from linaro_django_xmlrpc.models import AuthToken

class JSONDataError(ValueError):
    """Error raised when JSON is syntactically valid but ill-formed."""


class Tag(models.Model):

    name = models.SlugField(unique=True)

    description = models.TextField(null=True, blank=True)

    def __unicode__(self):
        return self.name


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
    OFFLINING = 3

    STATUS_CHOICES = (
        (OFFLINE, 'Offline'),
        (IDLE, 'Idle'),
        (RUNNING, 'Running'),
        (OFFLINING, 'Going offline'),
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

    tags = models.ManyToManyField(Tag, blank=True)

    status = models.IntegerField(
        choices = STATUS_CHOICES,
        default = IDLE,
        verbose_name = _(u"Device status"),
    )

    def __unicode__(self):
        return self.hostname

    @models.permalink
    def get_absolute_url(self):
        return ("lava.scheduler.device.detail", [self.pk])

    def recent_jobs(self):
        return TestJob.objects.select_related(
            "actual_device",
            "requested_device",
            "requested_device_type",
            "submitter",
        ).filter(
            actual_device=self
        ).order_by(
            '-start_time'
        )

    def can_admin(self, user):
        return user.has_perm('lava_scheduler_app.change_device')

    def put_into_maintenance_mode(self):
        if self.status == self.RUNNING:
            self.status = self.OFFLINING
        else:
            self.status = self.OFFLINE
        self.save()

    def put_into_online_mode(self):
        self.status = self.IDLE
        self.save()

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
    CANCELING = 5

    STATUS_CHOICES = (
        (SUBMITTED, 'Submitted'),
        (RUNNING, 'Running'),
        (COMPLETE, 'Complete'),
        (INCOMPLETE, 'Incomplete'),
        (CANCELED, 'Canceled'),
        (CANCELING, 'Canceling'),
    )

    id = models.AutoField(primary_key=True)

    submitter = models.ForeignKey(
        User,
        verbose_name = _(u"Submitter"),
    )

    submit_token = models.ForeignKey(AuthToken, null=True)

    description = models.CharField(
        verbose_name = _(u"Description"),
        max_length = 200,
        null = True,
        blank = True,
        default = None
    )

    # Only one of these two should be non-null.
    requested_device = models.ForeignKey(
        Device, null=True, default=None, related_name='+', blank=True)
    requested_device_type = models.ForeignKey(
        DeviceType, null=True, default=None, related_name='+', blank=True)

    tags = models.ManyToManyField(Tag, blank=True)

    # This is set once the job starts.
    actual_device = models.ForeignKey(
        Device, null=True, default=None, related_name='+', blank=True)

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
    log_file = models.FileField(
        upload_to='lava-logs', default=None, null=True, blank=True)

    results_link = models.CharField(
        max_length=400, default=None, null=True, blank=True)

    def __unicode__(self):
        r = "%s test job" % self.get_status_display()
        if self.requested_device:
            r += " for %s" % (self.requested_device.hostname,)
        return r

    @models.permalink
    def get_absolute_url(self):
        return ("lava.scheduler.job.detail", [self.pk])

    @classmethod
    def from_json_and_user(cls, json_data, user):
        job_data = simplejson.loads(json_data)
        if 'target' in job_data:
            target = Device.objects.get(hostname=job_data['target'])
            device_type = None
        elif 'device_type' in job_data:
            target = None
            device_type = DeviceType.objects.get(name=job_data['device_type'])
        else:
            raise JSONDataError(
                "Neither 'target' nor 'device_type' found in job data.")
        job_name = job_data.get('job_name', '')
        job = TestJob(
            definition=json_data, submitter=user, requested_device=target,
            requested_device_type=device_type, description=job_name)
        job.save()
        for tag_name in job_data.get('device_tags', []):
            job.tags.add(Tag.objects.get_or_create(name=tag_name)[0])
        return job

    def can_cancel(self, user):
        return user.is_superuser or user == self.submitter

    def cancel(self):
        if self.status == TestJob.RUNNING:
            self.status = TestJob.CANCELING
        else:
            self.status = TestJob.CANCELED
        self.save()
