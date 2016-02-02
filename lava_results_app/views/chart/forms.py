# Copyright (C) 2015 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# This file is part of Lava Server.
#
# Lava Server is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Lava Server is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Lava Server.  If not, see <http://www.gnu.org/licenses/>.

import datetime
import simplejson

from django import forms
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.forms.models import inlineformset_factory
from django.utils.html import escape

from dashboard_app.models import NamedAttribute

from lava_results_app.models import (
    Chart,
    ChartGroup,
    ChartQuery,
    ChartQueryUser,
    TestCase
)
from lava_scheduler_app.models import TestJob


class ChartForm(forms.ModelForm):
    class Meta:
        model = Chart
        exclude = ('is_published', 'chart_group', 'group', 'queries')
        widgets = {'owner': forms.HiddenInput}

    def __init__(self, owner, *args, **kwargs):
        super(ChartForm, self).__init__(*args, **kwargs)

    def save(self, commit=True, **kwargs):
        instance = super(ChartForm, self).save(commit=commit, **kwargs)
        return instance


class ChartQueryForm(forms.ModelForm):
    class Meta:
        model = ChartQuery
        exclude = ()
        widgets = {'chart': forms.HiddenInput,
                   'query': forms.HiddenInput,
                   'relative_index': forms.HiddenInput}

    def __init__(self, user, *args, **kwargs):
        super(ChartQueryForm, self).__init__(*args, **kwargs)

    def save(self, commit=True, **kwargs):
        instance = super(ChartQueryForm, self).save(commit=commit, **kwargs)
        return instance

    def clean(self):
        form_data = self.cleaned_data

        try:
            # Chart type validation.
            if form_data["query"].content_type.model_class() == TestCase and \
               form_data["chart_type"] == "pass/fail":
                self.add_error(
                    "chart_type",
                    "Pass/fail is incorrect value for 'chart_type' with TestCase based queries.")

        except KeyError:
            # form_data will pick up the rest of validation errors.
            pass

        return form_data


class ChartQueryUserForm(forms.ModelForm):
    class Meta:
        model = ChartQueryUser
        exclude = ['user', 'chart_query']

    def __init__(self, user, *args, **kwargs):
        super(ChartQueryUserForm, self).__init__(*args, **kwargs)
