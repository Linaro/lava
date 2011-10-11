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
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _

from lava_projects.models import Project


class _ProjectForm(forms.Form):
    """
    Mix-in with common project fields.
    """

    name = forms.CharField(
        label=_(u"Projet name"),
        help_text=_(u"Any name of your liking, can be updated later if you"
                    u" change your mind"),
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
                    u" distribution. Some UI elements are optimized for that"
                    u" case and behave differently."),
        required=False)

    def restrict_group_selection_for_user(self, user):
        assert user is not None
        self.fields['group'].queryset = user.groups.all()


class ProjectRegistrationForm(_ProjectForm):
    """
    Form for registering new projects.
    """

    identifier = forms.CharField(
        label=_(u"Identifier"),
        help_text=_(u"A unique identifier built from restricted subset of"
                    u" characters (only basic lowercase letters, numbers and"
                    u" dash)"),
        required=True,
        max_length=100)

    def __init__(self, *args, **kwargs):
        super(ProjectRegistrationForm, self).__init__(*args, **kwargs)
        self._reorder_fields(['name', 'identifier'])

    def _reorder_fields(self, first):
        for field in reversed(first):
            self.fields.keyOrder.remove(field)
            self.fields.keyOrder.insert(0, field)

    def clean_identifier(self):
        """
        Check that the identifier is correct:

            1) It does not collide with other projects
            2) Or their past identifiers
        """
        value = self.cleaned_data['identifier']
        try:
            # Lookup project that is, or was, this identifier
            project = Project.objects.all().get_by_identifier(value)
            if project.identifier == value:
                # Disallow current identifiers from other projects
                raise ValidationError(
                    "Project {0} is already using this identifier".format(
                        project))
            else:
                # Disallow past identifiers from other projects
                raise ValidationError(
                    "Project {0} was using this identifier in the past".format(
                        project))
        except Project.DoesNotExist:
            pass
        return value


class ProjectUpdateForm(_ProjectForm):
    """
    Form for updating project data
    """


class ProjectRenameForm(forms.Form):
    """
    Form for changing the project identifier
    """

    name = forms.CharField(
        label=_(u"Projet name"),
        help_text=_(u"The new project name, same limits as before "
                    u"(100 chars)"),
        required=True,
        max_length=100)

    identifier = forms.CharField(
        label=_(u"New identifier"),
        help_text=_(u"The new identifier has to be different from any current"
                    u" or past identifier used by other projects."),
        required=True,
        max_length=100)

    def __init__(self, project, *args, **kwargs):
        super(ProjectRenameForm, self).__init__(*args, **kwargs)
        self.project = project

    def clean_identifier(self):
        """
        Check that new identifier is correct:

            1) It does not collide with other projects
            2) Or their past identifiers
            3) It is different than the one we are currently using
        """
        value = self.cleaned_data['identifier']
        try:
            # Lookup project that is, or was, using this identifier
            project = Project.objects.all().get_by_identifier(value)
            if project == self.project and project.identifier != value:
                # Allow reusing identifiers inside one project
                pass
            elif project == self.project and project.identifier == value:
                raise ValidationError(
                    _(u"The new identifier has to be different than the one"
                      u"you are currently using"))
            elif project.identifier == value:
                # Disallow current identifiers from other projects
                raise ValidationError(
                    _(u"Project {0} is already using this identifier").format(
                        project))
            else:
                # Disallow past identifiers from other projects
                raise ValidationError(
                    _(u"Project {0} was using this identifier in the"
                      u"past").format(project))
        except Project.DoesNotExist:
            pass
        return value
