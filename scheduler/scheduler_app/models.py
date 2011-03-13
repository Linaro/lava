from django.db import models
from django.forms import ModelForm
import django.forms as forms
from fields import JSONField
from django.utils.translation import ugettext as _

class Device(models.Model):
    """
    Model for supported devices (boards)
    """
    device_name = models.CharField(
        verbose_name = _(u"Device name"),
        max_length = 200
    )
    device_type = models.CharField(
        verbose_name = _(u"Device type"),
        max_length = 200
    )
    hostname = models.CharField(
        verbose_name = _(u"Hostname"),
        max_length = 200
    )
    status = models.CharField(
        verbose_name = _(u"Device status"),
        max_length = 200,
        editable = False
    )

    def __unicode__(self):
        return self.device_name

class Test(models.Model):
    """
    Model for supported tests and test suites
    """
    test_name = models.CharField(
        verbose_name = _(u"Test name"),
        max_length = 200
    )
    path = models.CharField(
        verbose_name = _(u"Path"),
        max_length = 500
    )

    def __unicode__(self):
        return self.test_name

class TestJob(models.Model):
    """
    Model for submitted test jobs
    """
    user_name = models.CharField(
        verbose_name = _(u"User name"),
        max_length = 200
    )
    job_name = models.CharField(
        verbose_name = _(u"Test job name"),
        max_length = 200
    )
    target = models.ForeignKey(Device)
    timeout = models.IntegerField(verbose_name = _(u"Test job timeout"))
    priority = models.IntegerField(verbose_name = _(u"Priority"))
    tests = models.ForeignKey(Test)
    submit_time = models.DateTimeField(
        verbose_name = _(u"Submit time"),
        auto_now = False,
        auto_now_add = True
    )    
    end_time = models.DateTimeField(
        verbose_name = _(u"Test job end time"),
        auto_now = False,
        auto_now_add = False,
        null = True,
        blank = True,
        editable = False
    )    
    status = models.CharField(
        verbose_name = _(u"Test job status"),
        max_length = 200,
        editable = False
    )    
    raw_test_job = JSONField(
        blank = True,
        editable = False
    )

    def __unicode__(self):
        return self.job_name

class Action(models.Model):
    """
    Model for test job actions
    """
    name = models.CharField(
        verbose_name = _(u"Action name"),
        max_length = 200
    )
    tests = models.ManyToManyField(Test)
    parameters = JSONField(
        blank = True
    )

    def __unicode__(self):
        return self.name
    
class TestJobForm(ModelForm):
    """
    Form for test jobs, showing two extra fields not present in the model
    """
    rootfs = forms.URLField(
        label = _(u"Build image URL"),
        verify_exists = False,
        max_length = 500
    )    
    hwpack = forms.URLField(
        label = _(u"HW pack URL"),
        verify_exists = False,
        max_length = 500
    )

    class Meta:
        model = TestJob
