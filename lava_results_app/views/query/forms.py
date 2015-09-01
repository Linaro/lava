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

from django import forms
from django.forms.models import inlineformset_factory

from lava_results_app.models import (
    Query,
    QueryCondition,
    QueryGroup,
)


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


FIELD_CHOICES = {
    "testjob": ["submitter", "start_time", "end_time", "status",
                "actual_device", "health_check", "user", "group", "priority",
                "is_pipeline"],
    "testsuite": ["name"],
    "testcase": ["name", "result", "measurement"],
    "namedattribute": []
}


class QueryConditionForm(forms.ModelForm):
    class Meta:
        model = QueryCondition
        widgets = {
            'query': forms.HiddenInput,
            'table': forms.HiddenInput
        }

    def __init__(self, user, *args, **kwargs):
        super(QueryConditionForm, self).__init__(*args, **kwargs)

    def save(self, commit=True, **kwargs):
        return super(QueryConditionForm, self).save(commit=commit, **kwargs)

    def clean(self):
        form_data = self.cleaned_data
        # TODO: do field 'field' validation here based on selected table
        # FIELD_CHOICES
        try:
            if FIELD_CHOICES[form_data["table"].model]:
                if form_data["field"] not in \
                   FIELD_CHOICES[form_data["table"].model]:
                    self.add_error("field",
                                   "Allowed choices for 'field' are: %s" %
                                   (", ".join(FIELD_CHOICES[form_data[
                                       "table"].model])))
        except KeyError:
            # form_data will pick up the validation errors by itself.
            pass

        return form_data
