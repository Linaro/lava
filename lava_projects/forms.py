# Copyright (C) 2010, 2011 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of LAVA Server.
#
# LAVA Server is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA Server is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA Server.  If not, see <http://www.gnu.org/licenses/>.

from django import forms
from django.contrib.auth.models import Group
from django.utils.translation import ugettext as _


class ProjectForm(forms.Form):
    """
    Form for working with Project instances.
    ModelForm does not cut it for me :/
    """

    name = forms.CharField(
        label=_(u"Projet name"),
        help_text=_(u"Any name of your liking, can be updated later if you"
                    u" change your mind"),
        required=True,
        max_length=100)

    identifier = forms.CharField(
        label=_(u"Identifier"),
        help_text=_(u"A unique identifier built from restricted subset of"
                    u" characters (only basic lowercase letters, numbers and"
                    u" dash)"),
        required=True,
        max_length=100)

    description = forms.CharField(
        label=_(u"Description"),
        help_text=_(u"Arbitrary text about the project, you can use markdown"
                    u" formatting to style it"),
        widget=forms.widgets.Textarea(),
        required=False)

    group = forms.ModelChoiceField(
        label=_(u"Group owner"),
        help_text=_(u"Members of the selected group will co-own this project"),
        empty_label=_("None, I'll be the owner"),
        required=False,
        queryset=Group.objects.all())

    is_public = forms.BooleanField(
        label=_(u"Project is public"),
        help_text=_(u"If selected then this project will be visible to anyone."
                    u" Otherwise only owners can see the project"),
        required=False)

    is_aggregate = forms.BooleanField(
        label=_(u"Project is an aggregation (distribution)"),
        help_text=_(u"If selected the project will be treated like a"
                    u" distribution. Some UI elements are optimized for that case"
                    u" and behave differently."),
        required=False)

    def restrict_group_selection_for_user(self, user):
        assert user is not None
        self.fields['group'].queryset = user.groups.all()
