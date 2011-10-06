from django import forms
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _

from lava_projects.models import Project
from dashboard_app.models import TestingEffort


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
