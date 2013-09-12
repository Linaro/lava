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

from django import forms

from dashboard_app.models import (
    ImageReport,
    ImageReportChart,
    ImageChartFilter,
    ImageChartTest,
    ImageChartTestCase,
    Test,
    TestCase,
)


class ImageReportEditorForm(forms.ModelForm):
    class Meta:
        model = ImageReport
        exclude = ('owner', 'is_published',)

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
        widgets = {'image_report': forms.HiddenInput}

    def __init__(self, user, *args, **kwargs):
        super(ImageReportChartForm, self).__init__(*args, **kwargs)

    def save(self, commit=True, **kwargs):
        instance = super(ImageReportChartForm,
                         self).save(commit=commit, **kwargs)
        return instance


class ImageChartFilterForm(forms.ModelForm):

    image_chart_tests = forms.ModelMultipleChoiceField(
        widget=forms.MultipleHiddenInput,
        queryset=Test.objects.all(),
        required=False)
    image_chart_test_cases = forms.ModelMultipleChoiceField(
        widget=forms.MultipleHiddenInput,
        queryset=TestCase.objects.all(),
        required=False)

    class Meta:
        model = ImageChartFilter
        widgets = {'filter': forms.HiddenInput,
                   'image_chart': forms.HiddenInput,}

    def __init__(self, user, *args, **kwargs):
        super(ImageChartFilterForm, self).__init__(*args, **kwargs)

    def save(self, commit=True, **kwargs):
        instance = super(ImageChartFilterForm,
                         self).save(commit=commit, **kwargs)
        return instance
