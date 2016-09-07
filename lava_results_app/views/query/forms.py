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
from django.db import models
from django.utils.html import escape

from lava_results_app.models import (
    Query,
    QueryCondition,
)


class QueryForm(forms.ModelForm):
    class Meta:
        model = Query
        exclude = ('is_published', 'query_group', 'group', 'is_changed',
                   'last_updated', 'is_updating')
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

    def clean(self):
        form_data = self.cleaned_data

        try:
            # Existing (or archived) Query validataion.
            existing_query = Query.objects.get(name=form_data["name"],
                                               owner=form_data["owner"])
            if existing_query:
                if existing_query.is_archived:
                    self.add_error(
                        "name",
                        """ Query already exists but is archived. Please
                        contact system adminstrator or consult LAVA doc. """)
                elif not self.instance.id:
                    self.add_error(
                        "name",
                        "Query with this owner and name already exists.")
        except KeyError:
            # form_data will pick up the rest of validation errors.
            pass
        except Query.DoesNotExist:
            pass

        return form_data


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

    def __init__(self, *args, **kwargs):
        super(QueryConditionForm, self).__init__(*args, **kwargs)

        if "query" in self.initial and \
           self.initial['query'].__class__ == Query:
            condition_choices = QueryCondition.get_condition_choices()

            self.fields['condition_choices'].initial = simplejson.dumps(
                condition_choices)

    def save(self, commit=True, **kwargs):
        return super(QueryConditionForm, self).save(commit=commit, **kwargs)

    def clean(self):
        form_data = self.cleaned_data

        try:
            # Field validation.
            field_choices = QueryCondition.FIELD_CHOICES[
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
                if choices and form_data["value"] not in \
                   dict(choices).values():
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
