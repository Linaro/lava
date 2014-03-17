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
    ImageChartUser,
    Test,
    TestCase,
)


class ImageReportEditorForm(forms.ModelForm):
    class Meta:
        model = ImageReport
        exclude = ('is_published', 'image_report_group')
        widgets = {'user': forms.HiddenInput}

    def __init__(self, user, *args, **kwargs):
        super(ImageReportEditorForm, self).__init__(*args, **kwargs)

    def save(self, commit=True, **kwargs):
        instance = super(ImageReportEditorForm,
                         self).save(commit=commit, **kwargs)
        return instance


class ImageReportChartForm(forms.ModelForm):
    class Meta:
        model = ImageReportChart
        widgets = {'image_report': forms.HiddenInput}

    def __init__(self, user, *args, **kwargs):
        super(ImageReportChartForm, self).__init__(*args, **kwargs)
        if len(self.instance.imagechartfilter_set.all()) != 0:
            self.fields['chart_type'].label = ""
            self.fields['chart_type'].widget = forms.HiddenInput()

    def save(self, commit=True, **kwargs):
        instance = super(ImageReportChartForm,
                         self).save(commit=commit, **kwargs)
        return instance


class ImageChartFilterForm(forms.ModelForm):

    image_chart_tests = forms.ModelMultipleChoiceField(
        widget=forms.MultipleHiddenInput,
        queryset=Test.objects.all().order_by("id"),
        required=False)
    image_chart_test_cases = forms.ModelMultipleChoiceField(
        widget=forms.MultipleHiddenInput,
        queryset=TestCase.objects.all().order_by("id"),
        required=False)

    class Meta:
        model = ImageChartFilter
        widgets = {'filter': forms.HiddenInput,
                   'image_chart': forms.HiddenInput}

    def __init__(self, user, *args, **kwargs):
        super(ImageChartFilterForm, self).__init__(*args, **kwargs)

    def save(self, commit=True, **kwargs):
        instance = super(ImageChartFilterForm,
                         self).save(commit=commit, **kwargs)
        return instance


class ImageChartUserForm(forms.ModelForm):
    class Meta:
        model = ImageChartUser
        exclude = ['user', 'image_chart']

    def __init__(self, user, *args, **kwargs):
        super(ImageChartUserForm, self).__init__(*args, **kwargs)
