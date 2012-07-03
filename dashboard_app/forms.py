from django import forms
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _

from lava_projects.models import Project
from dashboard_app.models import TestingEffort, BundleStream


class TestingEffortForm(forms.Form):

    name = forms.CharField(
        label=_(u"Name"),
        max_length=100)

    description = forms.CharField(
        required=False,
        widget=forms.widgets.Textarea(),
        label=_(u"Description"),
        help_text=_(u"Description of this testing effort"))

    tags = forms.CharField(
        required=False,
        label=_(u"Tags"),
        max_length=1024,
        help_text=_(u"Tags, separated by whitespace or commas"))

class UserNotificationForm(forms.Form):
    #Fields: by_bundle_stream
    
    def __init__(self, user, *args, **kwargs):
        super(UserNotificationForm, self).__init__(*args, **kwargs)
        self.user = user
        self.fields['by_bundle_stream'] = forms.ModelMultipleChoiceField(
            queryset=BundleStream.objects.accessible_by_principal(self.user))

