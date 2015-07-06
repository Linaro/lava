# Copyright (C) 2010-2013 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# This file is part of Lava Dashboard.
#
# Lava Dashboard is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Lava Dashboard is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Lava Dashboard.  If not, see <http://www.gnu.org/licenses/>.

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
        exclude = ('is_published', 'image_report_group', 'group')
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
        fields = '__all__'
        widgets = {
            'image_report': forms.HiddenInput,
            'relative_index': forms.HiddenInput
        }

    xaxis_attribute_changed = forms.BooleanField(
        widget=forms.widgets.HiddenInput,
        required=False,
        initial=False
    )

    def __init__(self, user, *args, **kwargs):
        super(ImageReportChartForm, self).__init__(*args, **kwargs)
        if len(self.instance.imagechartfilter_set.all()) != 0:
            self.fields['chart_type'].label = ""
            self.fields['chart_type'].widget = forms.HiddenInput()

        if not self.instance.imagechartfilter_set.all() or \
           self.instance.chart_type == "attributes":
            self.fields['xaxis_attribute'].label = ""
            self.fields['xaxis_attribute'].widget = forms.HiddenInput()
        else:
            custom_attrs = self.instance.get_supported_attributes(user)

            if custom_attrs:
                self.fields['xaxis_attribute'] = forms.TypedChoiceField(
                    required=False,
                    choices=[("", "----")] +
                    [(attr, attr) for attr in custom_attrs],
                )
            else:
                self.fields['xaxis_attribute'].label = ""
                self.fields['xaxis_attribute'].widget = forms.HiddenInput()

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
        fields = '__all__'
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
