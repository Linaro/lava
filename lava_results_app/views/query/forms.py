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
    Query,
    QueryCondition,
    QueryGroup,
    TestCase,
    TestSuite
)
from lava_scheduler_app.models import TestJob


class QueryForm(forms.ModelForm):
    class Meta:
        model = Query
        exclude = ('is_published', 'query_group', 'group', 'is_changed',
                   'is_updating')
        widgets = {'owner': forms.HiddenInput}

    def __init__(self, owner, *args, **kwargs):
        is_copy = kwargs.pop('is_copy', None)
        super(QueryForm, self).__init__(*args, **kwargs)
        if is_copy:
            from copy import deepcopy
            self.instance = deepcopy(self.instance)
            self.instance.id = None
            self.instance.pk = None

    def save(self, commit=True, **kwargs):
        instance = super(QueryForm, self).save(commit=commit, **kwargs)
        return instance


class QueryConditionForm(forms.ModelForm):

    class Meta:
        model = QueryCondition
        fields = ('table', 'query', 'field', 'operator', 'value')
        widgets = {
            'query': forms.HiddenInput,
        }

    condition_choices = forms.CharField(
        widget=forms.HiddenInput
    )

    FIELD_CHOICES = {
        TestJob: [
            "submitter", "start_time", "end_time", "status", "actual_device",
            "health_check", "user", "group", "priority", "is_pipeline"],
        TestSuite: ["name"],
        TestCase: ["name", "result", "measurement"],
        NamedAttribute: []
    }

    def __init__(self, *args, **kwargs):
        super(QueryConditionForm, self).__init__(*args, **kwargs)

        if "query" in self.initial and \
           self.initial['query'].__class__ == Query:
            condition_choices = self._get_condition_choices()

            self.fields['condition_choices'].initial = simplejson.dumps(
                condition_choices)

    def save(self, commit=True, **kwargs):
        return super(QueryConditionForm, self).save(commit=commit, **kwargs)

    def clean(self):
        form_data = self.cleaned_data

        try:
            # Field validation.
            field_choices = self.FIELD_CHOICES[
                form_data["table"].model_class()]
            if field_choices:
                if form_data["field"] not in field_choices:
                    self.add_error("field",
                                   "Valid choices for 'field' are: %s" %
                                   (", ".join(field_choices)))
            # Choices validation
            field_object = form_data["table"].model_class()._meta.\
                get_field_by_name(form_data["field"])[0]
            choices = field_object.choices
            if choices and form_data["value"] not in dict(choices).values():
                self.add_error("value",
                               "Valid choices for 'value' are: %s" %
                               (", ".join(dict(choices).values())))

            if isinstance(field_object, models.DateTimeField):
                try:
                    datetime.datetime.strptime(
                        form_data["value"],
                        settings.DATETIME_INPUT_FORMATS[0])
                except ValueError:
                    self.add_error("value",
                                   "Incorrect format for 'value', try: %s" %
                                   settings.DATETIME_INPUT_FORMATS[0])
        except KeyError:
            # form_data will pick up the rest of validation errors.
            pass

        return form_data

    def clean_value(self):
        value = escape(self.cleaned_data['value'])
        return value

    def _get_condition_choices(self):
        # Create a dict with all possible operators based on the all available
        # field types, used for cliend-side validation.

        condition_choices = {}
        for model in self.FIELD_CHOICES:
            condition_choice = {}

            content_type = ContentType.objects.get_for_model(model)
            condition_choice['fields'] = {}
            for field_name in self.FIELD_CHOICES[model]:
                field = {}

                field_object = content_type.model_class()._meta.\
                    get_field_by_name(field_name)[0]
                field['operators'] = _get_operators_for_field_type(
                    field_object)
                field['type'] = field_object.__class__.__name__
                if field_object.choices:
                    field['choices'] = [unicode(x) for x in dict(
                        field_object.choices).values()]

                condition_choice['fields'][field_name] = field

            condition_choices[content_type.id] = condition_choice
            condition_choices['date_format'] = settings.\
                DATETIME_INPUT_FORMATS[0]

        return condition_choices


def _get_operators_for_field_type(field_object):
    # Determine available operators depending on the field type.
    operator_dict = dict(QueryCondition.OPERATOR_CHOICES)

    if field_object.choices:
        operator_keys = [
            QueryCondition.EXACT,
            QueryCondition.ICONTAINS
        ]
    elif isinstance(field_object, models.DateTimeField):
        operator_keys = [QueryCondition.GT]
    elif isinstance(field_object, models.ForeignKey):
        operator_keys = [
            QueryCondition.EXACT,
            QueryCondition.IEXACT,
            QueryCondition.ICONTAINS
        ]
    elif isinstance(field_object, models.BooleanField):
        operator_keys = [QueryCondition.EXACT]
    elif isinstance(field_object, models.IntegerField):
        operator_keys = [
            QueryCondition.EXACT,
            QueryCondition.ICONTAINS,
            QueryCondition.GT,
            QueryCondition.LT
        ]
    elif isinstance(field_object, models.CharField):
        operator_keys = [
            QueryCondition.EXACT,
            QueryCondition.IEXACT,
            QueryCondition.ICONTAINS
        ]
    elif isinstance(field_object, models.TextField):
        operator_keys = [
            QueryCondition.EXACT,
            QueryCondition.IEXACT,
            QueryCondition.ICONTAINS
        ]
    else:  # Show all.
        operator_keys = [
            QueryCondition.EXACT,
            QueryCondition.IEXACT,
            QueryCondition.ICONTAINS,
            QueryCondition.GT,
            QueryCondition.LT
        ]

    operators = dict([(i, operator_dict[i]) for i in operator_keys if i in operator_dict])

    return operators
