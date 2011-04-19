from django import forms
from django.utils.translation import ugettext as _

from lava.scheduler.scheduler_app.models import TestJob, TestSuite


class TestJobForm(forms.ModelForm):
    """
    Form for TestJob model, extra fields added
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

    TEST_SUITE_CHOICES = [(0, '-- choose a test suite --'), ] + \
        [(ts.id, ts.name) for ts in TestSuite.objects.all()]
    test_suite = forms.ChoiceField(
        choices = TEST_SUITE_CHOICES,
        widget = forms.Select(attrs = {'onchange':'get_test_cases();'})
    )

    class Meta:
        model = TestJob
