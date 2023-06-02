# Copyright (C) 2015-2018 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django import forms

from lava_results_app.models import Chart, ChartQuery, ChartQueryUser, TestCase


class ChartForm(forms.ModelForm):
    class Meta:
        model = Chart
        exclude = ("is_published", "chart_group", "group", "queries")
        widgets = {"owner": forms.HiddenInput}

    def __init__(self, owner, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def save(self, commit=True, **kwargs):
        instance = super().save(commit=commit, **kwargs)
        return instance


class ChartQueryForm(forms.ModelForm):
    class Meta:
        model = ChartQuery
        exclude = ()
        widgets = {
            "chart": forms.HiddenInput,
            "query": forms.HiddenInput,
            "relative_index": forms.HiddenInput,
        }

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def save(self, commit=True, **kwargs):
        instance = super().save(commit=commit, **kwargs)
        return instance

    def clean(self):
        form_data = self.cleaned_data

        try:
            # Chart type validation.
            if (
                form_data["query"].content_type.model_class() == TestCase
                and form_data["chart_type"] == "pass/fail"
            ):
                self.add_error(
                    "chart_type",
                    "Pass/fail is incorrect value for 'chart_type' with TestCase based queries.",
                )

        except KeyError:
            # form_data will pick up the rest of validation errors.
            pass

        return form_data


class ChartQueryUserForm(forms.ModelForm):
    class Meta:
        model = ChartQueryUser
        exclude = ["user", "chart_query"]

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
