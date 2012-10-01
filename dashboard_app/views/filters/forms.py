# Copyright (C) 2010-2011 Linaro Limited
#
# Author: Michael Hudson-Doyle <michael.hudson@linaro.org>
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
from django.forms.widgets import Select
from django.template import Template, Context
from django.utils.safestring import mark_safe

from dashboard_app.models import (
    BundleStream,
    Test,
    TestCase,
    TestRunFilter,
    TestRunFilterSubscription,
)

class TestRunFilterSubscriptionForm(forms.ModelForm):
    class Meta:
        model = TestRunFilterSubscription
        fields = ('level',)
    def __init__(self, filter, user, *args, **kwargs):
        super(TestRunFilterSubscriptionForm, self).__init__(*args, **kwargs)
        self.instance.filter = filter
        self.instance.user = user



test_run_filter_head = '''
<link rel="stylesheet" type="text/css" href="{{ STATIC_URL }}dashboard_app/css/filter-edit.css" />
<script type="text/javascript" src="{% url admin:jsi18n %}"></script>
<script type="text/javascript">
var django = {};
django.jQuery = $;
var test_case_url = "{% url dashboard_app.views.filter_add_cases_for_test_json %}?test=";
var attr_name_completion_url = "{% url dashboard_app.views.filter_attr_name_completion_json %}";
var attr_value_completion_url = "{% url dashboard_app.views.filter_attr_value_completion_json %}";
</script>
<script type="text/javascript" src="{{ STATIC_URL }}dashboard_app/js/jquery.formset.js"></script>
<script type="text/javascript" src="{{ STATIC_URL }}dashboard_app/js/filter-edit.js"></script>
'''


class AttributesForm(forms.Form):
    name = forms.CharField(max_length=1024)
    value = forms.CharField(max_length=1024)

AttributesFormSet = formset_factory(AttributesForm, extra=0)


class TruncatingSelect(Select):

    def render_option(self, selected_choices, option_value, option_label):
        if len(option_label) > 50:
            option_label = option_label[:50] + '...'
        return super(TruncatingSelect, self).render_option(
            selected_choices, option_value, option_label)


class TRFTestCaseForm(forms.Form):

    test_case = forms.ModelChoiceField(
        queryset=TestCase.objects.none(), widget=TruncatingSelect, empty_label=None)


class BaseTRFTestCaseFormSet(BaseFormSet):

    def __init__(self, *args, **kw):
        self._queryset = kw.pop('queryset')
        super(BaseTRFTestCaseFormSet, self).__init__(*args, **kw)

    def add_fields(self, form, index):
        super(BaseTRFTestCaseFormSet, self).add_fields(form, index)
        if self._queryset is not None:
            form.fields['test_case'].queryset = self._queryset


TRFTestCaseFormSet = formset_factory(
    TRFTestCaseForm, extra=0, formset=BaseTRFTestCaseFormSet)


class TRFTestForm(forms.Form):

    def __init__(self, *args, **kw):
        super(TRFTestForm, self).__init__(*args, **kw)
        kw['initial'] = kw.get('initial', {}).get('test_cases', None)
        kw.pop('empty_permitted', None)
        kw['queryset'] = None
        v = self['test'].value()
        if v:
            test = self.fields['test'].to_python(v)
            queryset = TestCase.objects.filter(test=test).order_by('test_case_id')
            kw['queryset'] = queryset
        self.test_case_formset = TRFTestCaseFormSet(*args, **kw)

    def is_valid(self):
        return super(TRFTestForm, self).is_valid() and \
               self.test_case_formset.is_valid()

    def full_clean(self):
        super(TRFTestForm, self).full_clean()
        self.test_case_formset.full_clean()

    test = forms.ModelChoiceField(
        queryset=Test.objects.order_by('test_id'), required=True)


class BaseTRFTestsFormSet(BaseFormSet):

    def is_valid(self):
        if not super(BaseTRFTestsFormSet, self).is_valid():
            return False
        for form in self.forms:
            if not form.is_valid():
                return False
        return True


TRFTestsFormSet = formset_factory(
    TRFTestForm, extra=0, formset=BaseTRFTestsFormSet)


class FakeTRFTest(object):
    def __init__(self, form):
        self.test = form.cleaned_data['test']
        self.test_id = self.test.id
        self._case_ids = []
        self._case_names = []
        for tc_form in form.test_case_formset:
            self._case_ids.append(tc_form.cleaned_data['test_case'].id)
            self._case_names.append(tc_form.cleaned_data['test_case'].test_case_id)

    def all_case_ids(self):
        return self._case_ids

    def all_case_names(self):
        return self._case_names


class TestRunFilterForm(forms.ModelForm):
    class Meta:
        model = TestRunFilter
        exclude = ('owner',)
        widgets = {
            'bundle_streams': FilteredSelectMultiple("Bundle Streams", False),
            }

    @property
    def media(self):
        super_media = str(super(TestRunFilterForm, self).media)
        return mark_safe(Template(test_run_filter_head).render(
            Context({'STATIC_URL': settings.STATIC_URL})
            )) + super_media

    def validate_name(self, value):
        self.instance.name = value
        try:
            self.instance.validate_unique()
        except ValidationError, e:
            if e.message_dict.values() == [[
                u'Test run filter with this Owner and Name already exists.']]:
                raise ValidationError("You already have a filter with this name")
            else:
                raise

    def save(self, commit=True, **kwargs):
        instance = super(TestRunFilterForm, self).save(commit=commit, **kwargs)
        if commit:
            instance.attributes.all().delete()
            for a in self.attributes_formset.cleaned_data:
                instance.attributes.create(name=a['name'], value=a['value'])
            instance.tests.all().delete()
            for i, test_form in enumerate(self.tests_formset.forms):
                trf_test = instance.tests.create(
                    test=test_form.cleaned_data['test'], index=i)
                for j, test_case_form in enumerate(test_form.test_case_formset.forms):
                    trf_test.cases.create(
                        test_case=test_case_form.cleaned_data['test_case'], index=j)
        return instance

    def is_valid(self):
        return super(TestRunFilterForm, self).is_valid() and \
               self.attributes_formset.is_valid() and \
               self.tests_formset.is_valid()

    def full_clean(self):
        super(TestRunFilterForm, self).full_clean()
        self.attributes_formset.full_clean()
        self.tests_formset.full_clean()

    @property
    def summary_data(self):
        data = self.cleaned_data.copy()
        tests = []
        for form in self.tests_formset.forms:
            tests.append(FakeTRFTest(form))
        data['attributes'] = [
            (d['name'], d['value']) for d in self.attributes_formset.cleaned_data]
        data['tests'] = tests
        return data

    def __init__(self, user, *args, **kwargs):
        super(TestRunFilterForm, self).__init__(*args, **kwargs)
        self.instance.owner = user
        kwargs.pop('instance', None)

        attr_set_args = kwargs.copy()
        if self.instance.pk:
            initial = []
            for attr in self.instance.attributes.all():
                initial.append({
                    'name': attr.name,
                    'value': attr.value,
                    })
            attr_set_args['initial'] = initial
        attr_set_args['prefix'] = 'attributes'
        self.attributes_formset = AttributesFormSet(*args, **attr_set_args)

        tests_set_args = kwargs.copy()
        if self.instance.pk:
            initial = []
            for test in self.instance.tests.all().order_by('index').prefetch_related('cases'):
                initial.append({
                    'test': test.test,
                    'test_cases': [{'test_case': unicode(tc.test_case.id)} for tc in test.cases.all().order_by('index')],
                    })
            tests_set_args['initial'] = initial
        tests_set_args['prefix'] = 'tests'
        self.tests_formset = TRFTestsFormSet(*args, **tests_set_args)

        self.fields['bundle_streams'].queryset = \
            BundleStream.objects.accessible_by_principal(user).order_by('pathname')
        self.fields['name'].validators.append(self.validate_name)

    def get_test_runs(self, user):
        assert self.is_valid(), self.errors
        filter = self.save(commit=False)
        tests = []
        for form in self.tests_formset.forms:
            tests.append(FakeTRFTest(form))
        return filter.get_test_runs_impl(
            user, self.cleaned_data['bundle_streams'], self.summary_data['attributes'], tests)

