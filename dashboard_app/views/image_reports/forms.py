# Copyright (C) 2010-2013 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

from django.conf import settings
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.core.exceptions import ValidationError
from django import forms
from django.forms.formsets import BaseFormSet, formset_factory
from django.forms.widgets import Select, HiddenInput
from django.template import Template, Context
from django.utils.safestring import mark_safe

from dashboard_app.models import (
    ImageReport,
    ImageReportChart,
)


class ImageReportEditorForm(forms.ModelForm):
    class Meta:
        model = ImageReport
        exclude = ('owner',)
        widgets = {
        #'bundle_streams': FilteredSelectMultiple("Bundle Streams", False),
            }

    # def validate_name(self, value):
    #     self.instance.name = value
    #     try:
    #         self.instance.validate_unique()
    #     except ValidationError, e:
    #         if e.message_dict.values() == [[
    #             u'Test run filter with this Owner and Name already exists.']]:
    #             raise ValidationError("You already have a filter with this name")
    #         else:
    #             raise

    def save(self, commit=True, **kwargs):
        instance = super(ImageReportEditorForm,
                         self).save(commit=commit, **kwargs)
        return instance

    def is_valid(self):
        return super(ImageReportEditorForm, self).is_valid()

    def full_clean(self):
        super(ImageReportEditorForm, self).full_clean()

    def __init__(self, user, *args, **kwargs):
        super(ImageReportEditorForm, self).__init__(*args, **kwargs)


class ImageReportChartForm(forms.ModelForm):
    class Meta:
        model = ImageReportChart
        exclude = ('owner',)
        widgets = {'image_report': forms.HiddenInput}

    def __init__(self, user, *args, **kwargs):
        super(ImageReportChartForm, self).__init__(*args, **kwargs)

    def save(self, commit=True, **kwargs):
        instance = super(ImageReportChartForm,
                         self).save(commit=commit, **kwargs)
        return instance
