# Copyright (C) 2015-2018 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import contextlib
import datetime
from json import dumps as json_dumps

from django import forms
from django.conf import settings
from django.db import models
from django.utils.html import escape

from lava_results_app.models import Query, QueryCondition


class QueryForm(forms.ModelForm):
    class Meta:
        model = Query
        exclude = (
            "is_published",
            "query_group",
            "group",
            "is_changed",
            "last_updated",
            "is_updating",
        )
        widgets = {"owner": forms.HiddenInput}

    def __init__(self, owner, *args, **kwargs):
        is_copy = kwargs.pop("is_copy", None)
        super().__init__(*args, **kwargs)
        if is_copy:
            from copy import deepcopy

            self.instance = deepcopy(self.instance)
            self.instance.id = None
            self.instance.pk = None

    def save(self, commit=True, **kwargs):
        instance = super().save(commit=commit, **kwargs)
        return instance

    def clean(self):
        form_data = self.cleaned_data

        with contextlib.suppress(KeyError, Query.DoesNotExist):
            # Existing (or archived) Query validation.
            existing_query = Query.objects.get(
                name=form_data["name"], owner=form_data["owner"]
            )
            if existing_query:
                if existing_query.is_archived:
                    self.add_error(
                        "name",
                        """ Query already exists but is archived. Please
                        contact system administrator or consult LAVA doc. """,
                    )
                elif not self.instance.id:
                    self.add_error(
                        "name", "Query with this owner and name already exists."
                    )

        return form_data


class QueryConditionForm(forms.ModelForm):
    class Meta:
        model = QueryCondition
        fields = ("table", "query", "field", "operator", "value")
        widgets = {"query": forms.HiddenInput}

    condition_choices = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "query" in self.initial and self.initial["query"].__class__ == Query:
            condition_choices = QueryCondition.get_condition_choices()

            self.fields["condition_choices"].initial = json_dumps(condition_choices)

    def save(self, commit=True, **kwargs):
        return super().save(commit=commit, **kwargs)

    def clean(self):
        form_data = self.cleaned_data

        try:
            # Field validation.
            field_choices = QueryCondition.FIELD_CHOICES[
                form_data["table"].model_class()
            ]
            if field_choices:
                if form_data["field"] not in field_choices:
                    self.add_error(
                        "field",
                        "Valid choices for 'field' are: %s"
                        % (", ".join(field_choices)),
                    )

                # Choices validation
                field_object = (
                    form_data["table"].model_class()._meta.get_field(form_data["field"])
                )
                choices = field_object.choices
                if choices and form_data["value"] not in dict(choices).values():
                    self.add_error(
                        "value",
                        "Valid choices for 'value' are: %s"
                        % (", ".join([str(x) for x in dict(choices).values()])),
                    )

                if isinstance(field_object, models.DateTimeField):
                    try:
                        datetime.datetime.strptime(
                            form_data["value"], settings.DATETIME_INPUT_FORMATS[0]
                        )
                    except ValueError:
                        self.add_error(
                            "value",
                            "Incorrect format for 'value', try: %s"
                            % settings.DATETIME_INPUT_FORMATS[0],
                        )
        except KeyError:
            # form_data will pick up the rest of validation errors.
            pass

        return form_data

    def clean_value(self):
        value = escape(self.cleaned_data["value"])
        return value
