# Copyright (C) 2010-2012 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
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

"""
Views for the Dashboard application
"""

import re
import json

from django.conf import settings
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth.decorators import login_required
from django.contrib.sites.models import Site
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.urlresolvers import reverse
from django.db.models.manager import Manager
from django.db.models.query import QuerySet
from django import forms
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response, redirect, get_object_or_404
from django.template import RequestContext, loader
from django.template import Template, Context
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST
from django.views.generic.list_detail import object_list, object_detail

from django_tables2 import Attrs, Column, TemplateColumn

from lava.utils.data_tables.tables import DataTablesTable
from lava_server.views import index as lava_index
from lava_server.bread_crumbs import (
    BreadCrumb,
    BreadCrumbTrail,
)

from dashboard_app.models import (
    Attachment,
    Bundle,
    BundleStream,
    DataReport,
    DataView,
    Image,
    ImageSet,
    LaunchpadBug,
    NamedAttribute,
    Tag,
    Test,
    TestCase,
    TestResult,
    TestRun,
    TestRunFilter,
    TestRunFilterSubscription,
    TestingEffort,
)


def _get_queryset(klass):
    """
    Returns a QuerySet from a Model, Manager, or QuerySet. Created to make
    get_object_or_404 and get_list_or_404 more DRY.
    """
    if isinstance(klass, QuerySet):
        return klass
    elif isinstance(klass, Manager):
        manager = klass
    else:
        manager = klass._default_manager
    return manager.all()


def get_restricted_object_or_404(klass, via, user, *args, **kwargs):
    """
    Uses get() to return an object, or raises a Http404 exception if the object
    does not exist. If the object exists access control check is made
    using the via callback (via is called with the found object and the return
    value must be a RestrictedResource subclass.

    klass may be a Model, Manager, or QuerySet object. All other passed
    arguments and keyword arguments are used in the get() query.

    Note: Like with get(), an MultipleObjectsReturned will be raised if more than one
    object is found.
    """
    queryset = _get_queryset(klass)
    try:
        obj = queryset.get(*args, **kwargs)
        ownership_holder = via(obj)
        if not ownership_holder.is_accessible_by(user):
            raise queryset.model.DoesNotExist()
        return obj
    except queryset.model.DoesNotExist:
        raise Http404('No %s matches the given query.' % queryset.model._meta.object_name)


@BreadCrumb("Dashboard", parent=lava_index)
def index(request):
    return render_to_response(
        "dashboard_app/index.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(index)
        }, RequestContext(request))




class BundleStreamTable(DataTablesTable):

    pathname = TemplateColumn(
        '<a href="{% url dashboard_app.views.bundle_list record.pathname %}">'
        '<code>{{ record.pathname }}</code></a>')
    name = TemplateColumn(
        '{{ record.name|default:"<i>not set</i>" }}')
    number_of_test_runs = TemplateColumn(
        '<a href="{% url dashboard_app.views.test_run_list record.pathname %}">'
        '{{ record.get_test_run_count }}')
    number_of_bundles = TemplateColumn(
        '<a href="{% url dashboard_app.views.bundle_list record.pathname %}">'
        '{{ record.bundles.count}}</a>')

    def get_queryset(self, user):
        return BundleStream.objects.accessible_by_principal(user)

    datatable_opts = {
        'iDisplayLength': 25,
        'sPaginationType': "full_numbers",
        }

    searchable_columns = ['pathname', 'name']


def bundle_stream_list_json(request):
    return BundleStreamTable.json(request, params=(request.user,))


@BreadCrumb("Bundle Streams", parent=index)
def bundle_stream_list(request):
    """
    List of bundle streams.
    """
    return render_to_response(
        'dashboard_app/bundle_stream_list.html', {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                bundle_stream_list),
            "bundle_stream_table": BundleStreamTable(
                'bundle-stream-table', reverse(bundle_stream_list_json),
                params=(request.user,)),
            'has_personal_streams': (
                request.user.is_authenticated() and
                BundleStream.objects.filter(user=request.user).count() > 0),
            'has_team_streams': (
                request.user.is_authenticated() and
                BundleStream.objects.filter(
                    group__in = request.user.groups.all()).count() > 0),
        }, RequestContext(request)
    )


class BundleTable(DataTablesTable):

    content_filename = TemplateColumn(
        '<a href="{{ record.get_absolute_url }}">'
        '<code>{{ record.content_filename }}</code></a>',
        verbose_name="bundle name")

    passes = TemplateColumn('{{ record.get_summary_results.pass|default:"0" }}')
    fails = TemplateColumn('{{ record.get_summary_results.fail|default:"0" }}')
    total_results = TemplateColumn('{{ record.get_summary_results.total }}')

    uploaded_on = TemplateColumn('{{ record.uploaded_on|date:"Y-m-d H:i:s"}}')
    uploaded_by = TemplateColumn('''
        {% load i18n %}
        {% if record.uploaded_by %}
            {{ record.uploaded_by }}
        {% else %}
            <em>{% trans "anonymous user" %}</em>
        {% endif %}''')
    deserializaled = TemplateColumn('{{ record.is_deserialized|yesno }}')

    def get_queryset(self, bundle_stream):
        return bundle_stream.bundles.select_related(
            'bundle_stream', 'deserialization_error')

    datatable_opts = {
        'aaSorting': [[4, 'desc']],
        'sPaginationType': 'full_numbers',
        'iDisplayLength': 25,
#        'aLengthMenu': [[10, 25, 50, -1], [10, 25, 50, "All"]],
        'sDom': 'lfr<"#master-toolbar">t<"F"ip>',
        }

    searchable_columns = ['content_filename']


def bundle_list_table_json(request, pathname):
    bundle_stream = get_restricted_object_or_404(
        BundleStream,
        lambda bundle_stream: bundle_stream,
        request.user,
        pathname=pathname
    )
    return BundleTable.json(request, params=(bundle_stream,))


@BreadCrumb(
    "Bundles in {pathname}",
    parent=bundle_stream_list,
    needs=['pathname'])
def bundle_list(request, pathname):
    """
    List of bundles in a specified bundle stream.
    """
    bundle_stream = get_restricted_object_or_404(
        BundleStream,
        lambda bundle_stream: bundle_stream,
        request.user,
        pathname=pathname
    )
    return render_to_response(
        "dashboard_app/bundle_list.html",
        {
            'bundle_table': BundleTable(
                'bundle-table',
                reverse(
                    bundle_list_table_json, kwargs=dict(pathname=pathname)),
                params=(bundle_stream,)),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                bundle_list,
                pathname=pathname),
            "bundle_stream": bundle_stream
            },
        RequestContext(request))


@BreadCrumb(
    "Bundle {content_sha1}",
    parent=bundle_list,
    needs=['pathname', 'content_sha1'])
def bundle_detail(request, pathname, content_sha1):
    """
    Detail about a bundle from a particular stream
    """
    bundle_stream = get_restricted_object_or_404(
        BundleStream,
        lambda bundle_stream: bundle_stream,
        request.user,
        pathname=pathname
    )
    return object_detail(
        request,
        queryset=bundle_stream.bundles.all(),
        slug=content_sha1,
        slug_field="content_sha1",
        template_name="dashboard_app/bundle_detail.html",
        template_object_name="bundle",
        extra_context={
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                bundle_detail,
                pathname=pathname,
                content_sha1=content_sha1),
            "site": Site.objects.get_current(),
            "bundle_stream": bundle_stream
        })


def bundle_json(request, pathname, content_sha1):
    bundle_stream = get_restricted_object_or_404(
        BundleStream,
        lambda bundle_stream: bundle_stream,
        request.user,
        pathname=pathname
    )
    bundle = bundle_stream.bundles.get(content_sha1=content_sha1)
    test_runs = []
    for test_run in bundle.test_runs.all():
        results = test_run.get_summary_results()

        measurements = [{'item': str(item.test_case),
                           'measurement': str(item.measurement),
                           'units': str(item.units)
                          }
                for item in test_run.test_results.filter(
                            measurement__isnull=False).
                        order_by('test_case__test_case_id')]
        results['measurements'] = measurements

        test_runs.append({
            'name': test_run.test.test_id,
            'url': request.build_absolute_uri(test_run.get_absolute_url()),
            'results': results
            })
    json_text = json.dumps({
        'test_runs':test_runs,
        })
    content_type = 'application/json'
    if 'callback' in request.GET:
        json_text = '%s(%s)'%(request.GET['callback'], json_text)
        content_type = 'text/javascript'
    return HttpResponse(json_text, content_type=content_type)


def ajax_bundle_viewer(request, pk):
    bundle = get_restricted_object_or_404(
        Bundle,
        lambda bundle: bundle.bundle_stream,
        request.user,
        pk=pk
    )
    return render_to_response(
        "dashboard_app/_ajax_bundle_viewer.html", {
            "bundle": bundle
        },
        RequestContext(request))


class TestRunTable(DataTablesTable):

    record = TemplateColumn(
        '<a href="{{ record.get_absolute_url }}">'
        '<code>{{ record.test }} results<code/></a>',
        accessor="test__test_id",
        )

    test = TemplateColumn(
        '<a href="{{ record.test.get_absolute_url }}">{{ record.test }}</a>',
        accessor="test__test_id",
        )

    uploaded_on = TemplateColumn(
        '{{ record.bundle.uploaded_on|date:"Y-m-d H:i:s" }}',
        accessor='bundle__uploaded_on')

    analyzed_on = TemplateColumn(
        '{{ record.analyzer_assigned_date|date:"Y-m-d H:i:s" }}',
        accessor='analyzer_assigned_date')

    def get_queryset(self, bundle_stream):
        return TestRun.objects.filter(
                bundle__bundle_stream=bundle_stream
            ).select_related(
                "test",
                "bundle",
                "bundle__bundle_stream",
                "test_results"
            ).only(
                "analyzer_assigned_uuid",  # needed by TestRun.__unicode__
                "analyzer_assigned_date",  # used by the view
                "bundle__uploaded_on",  # needed by Bundle.get_absolute_url
                "bundle__content_sha1",   # needed by Bundle.get_absolute_url
                "bundle__bundle_stream__pathname",  # Needed by TestRun.get_absolute_url
                "test__name",  # needed by Test.__unicode__
                "test__test_id",  # needed by Test.__unicode__
            )

    datatable_opts = {
        "sPaginationType": "full_numbers",
        "aaSorting": [[1, "desc"]],
        "iDisplayLength": 25,
        "sDom": 'lfr<"#master-toolbar">t<"F"ip>'
        }

    searchable_columns = ['test__test_id']


def test_run_list_json(request, pathname):
    bundle_stream = get_restricted_object_or_404(
        BundleStream,
        lambda bundle_stream: bundle_stream,
        request.user,
        pathname=pathname
    )
    return TestRunTable.json(request, params=(bundle_stream,))


@BreadCrumb(
    "Test runs in {pathname}",
    parent=bundle_stream_list,
    needs=['pathname'])
def test_run_list(request, pathname):
    """
    List of test runs in a specified bundle stream.
    """
    bundle_stream = get_restricted_object_or_404(
        BundleStream,
        lambda bundle_stream: bundle_stream,
        request.user,
        pathname=pathname
    )
    return render_to_response(
        'dashboard_app/test_run_list.html', {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                test_run_list,
                pathname=pathname),
            "test_run_table": TestRunTable(
                'test-runs',
                reverse(test_run_list_json, kwargs=dict(pathname=pathname)),
                params=(bundle_stream,)),
            "bundle_stream": bundle_stream,
        }, RequestContext(request)
    )


class TestTable(DataTablesTable):

    relative_index = Column(
        verbose_name="#", attrs=Attrs(th=dict(style="width: 1%")),
        default=mark_safe("<em>Not specified</em>"))

    test_case = Column()

    result = TemplateColumn('''
        <a href="{{record.get_absolute_url}}">
          <img src="{{ STATIC_URL }}dashboard_app/images/icon-{{ record.result_code }}.png"
          alt="{{ record.get_result_display }}" width="16" height="16" border="0"/></a>
        <a href ="{{record.get_absolute_url}}">{{ record.get_result_display }}</a>
        ''')

    units = TemplateColumn(
        '{{ record.measurement|default_if_none:"Not specified" }} {{ record.units }}',
        verbose_name="measurement")

    def get_queryset(self, test_run):
        return test_run.get_results()

    datatable_opts = {
        'sPaginationType': "full_numbers",
        }

    searchable_columns = ['test_case__test_case_id']


class UserFiltersTable(DataTablesTable):

    name = TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">{{ record.name }}</a>
    ''')

    bundle_streams = TemplateColumn('''
    {% for r in record.bundle_streams.all %}
        {{r.pathname}} <br />
    {% endfor %}
    ''')

    attributes = TemplateColumn('''
    {% for a in record.attributes.all %}
    {{ a }}  <br />
    {% endfor %}
    ''')

    test = TemplateColumn('''
    {% if record.test_case %}
        {{ record.test }}:{{ record.test_case }}
    {% elif record.test %}
        {{ record.test }}:&lt;any&gt;
    {% else %}
        &lt;any&gt;:&lt;any&gt;
    {% endif %}
    ''')

    subscription = Column()
    def render_subscription(self, record):
        try:
            sub = TestRunFilterSubscription.objects.get(
                user=self.user, filter=record)
        except TestRunFilterSubscription.DoesNotExist:
            return "None"
        else:
            return sub.get_level_display()

    public = Column()

    def get_queryset(self, user):
        return TestRunFilter.objects.filter(owner=user)


class PublicFiltersTable(UserFiltersTable):

    name = TemplateColumn('''
    <a href="{{ record.get_absolute_url }}">~{{ record.owner.username }}/{{ record.name }}</a>
    ''')

    def __init__(self, *args, **kw):
        super(PublicFiltersTable, self).__init__(*args, **kw)
        del self.base_columns['public']

    def get_queryset(self):
        return TestRunFilter.objects.filter(public=True)


@BreadCrumb("Filters and Subscriptions", parent=index)
def filters_list(request):
    public_filters_table = PublicFiltersTable("public-filters", None)
    if request.user.is_authenticated():
        public_filters_table.user = request.user
        user_filters_table = UserFiltersTable("user-filters", None, params=(request.user,))
        user_filters_table.user = request.user
    else:
        user_filters_table = None
        del public_filters_table.base_columns['subscription']

    return render_to_response(
        'dashboard_app/filters_list.html', {
            'user_filters_table': user_filters_table,
            'public_filters_table': public_filters_table,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                filters_list),
        }, RequestContext(request)
    )


class SpecificCaseColumn(Column):
    def render(self, value, record):
        r = []
        for result in value:
            if result.result == result.RESULT_PASS and result.units:
                s = '%s %s' % (result.measurement, result.units)
            else:
                s = result.RESULT_MAP[result.result]
            r.append('<a href="' + result.get_absolute_url() + '">'+s+'</a>')
        return mark_safe(', '.join(r))


class BundleColumn(Column):
    def render(self, record):
        return mark_safe('<a href="' + record.bundle.get_absolute_url() + '">' + escape(record.bundle.content_filename) + '</a>')


class FilterTable(DataTablesTable):
    def __init__(self, *args, **kwargs):
        filter = kwargs['params'][1]
        data = filter.summary_data
        super(FilterTable, self).__init__(*args, **kwargs)
        if len(data['bundle_streams']) == 1:
            del self.base_columns['bundle_stream']
        if data['test_case']:
            del self.base_columns['bundle']
            del self.base_columns['passes']
            del self.base_columns['total']
            self.base_columns['specific_results'].verbose_name = mark_safe(
                data['test_case'].test_case_id)
        elif data['test']:
            del self.base_columns['bundle']
            del self.base_columns['specific_results']
        else:
            del self.base_columns['test_run']
            self.base_columns['passes']
            self.base_columns['total']
            del self.base_columns['specific_results']
        uploaded_col_index = self.base_columns.keys().index('uploaded_on')
        self.datatable_opts = self.datatable_opts.copy()
        self.datatable_opts['aaSorting'] = [[uploaded_col_index, 'desc']]
        self._compute_queryset(kwargs['params'])

    bundle_stream = Column(accessor='bundle.bundle_stream')

    bundle = BundleColumn(accessor='bundle', sortable=False)

    test_run = TemplateColumn(
        '<a href="{{ record.test_run.get_absolute_url }}">'
        '<code>{{ record.test_run.test }} results<code/></a>',
        accessor="test__test_id",
        )

    uploaded_on = TemplateColumn(
        '{{ record.bundle.uploaded_on|date:"Y-m-d H:i:s" }}',
        accessor='bundle__uploaded_on')

    passes = Column(accessor='pass_count', sortable=False)
    total = Column(accessor='result_count', sortable=False)
    specific_results = SpecificCaseColumn(accessor='specific_results', sortable=False)
    def get_queryset(self, user, filter):
        return filter.get_test_runs(user)

    datatable_opts = {
        "sPaginationType": "full_numbers",
        "iDisplayLength": 25,
        }


def filter_json(request, username, name):
    filter = TestRunFilter.objects.get(owner__username=username, name=name)
    return FilterTable.json(request, params=(request.user, filter))


class FilterPreviewTable(FilterTable):
    def get_queryset(self, user, form):
        return form.get_test_runs(user)

    datatable_opts = FilterTable.datatable_opts.copy()
    datatable_opts.update({
        "iDisplayLength": 10,
        })


def filter_preview_json(request):
    try:
        filter = TestRunFilter.objects.get(owner=request.user, name=request.GET['name'])
    except TestRunFilter.DoesNotExist:
        filter = None
    form = TestRunFilterForm(request.user, request.GET, instance=filter)
    if not form.is_valid():
        raise ValidationError(str(form.errors))
    return FilterPreviewTable.json(request, params=(request.user, form))


@BreadCrumb("Filter ~{username}/{name}", parent=filters_list, needs=['username', 'name'])
def filter_detail(request, username, name):
    filter = TestRunFilter.objects.get(owner__username=username, name=name)
    if not filter.public and filter.owner != request.user:
        raise PermissionDenied()
    if not request.user.is_authenticated():
        subscription = None
    else:
        try:
            subscription = TestRunFilterSubscription.objects.get(
                user=request.user, filter=filter)
        except TestRunFilterSubscription.DoesNotExist:
            subscription = None
    return render_to_response(
        'dashboard_app/filter_detail.html', {
            'filter': filter,
            'subscription': subscription,
            'filter_table': FilterTable(
                "filter-table",
                reverse(filter_json, kwargs=dict(username=username, name=name)),
                params=(request.user, filter)),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                filter_detail, name=name, username=username),
        }, RequestContext(request)
    )


class TestRunFilterSubscriptionForm(forms.ModelForm):
    class Meta:
        model = TestRunFilterSubscription
        fields = ('level',)
    def __init__(self, filter, user, *args, **kwargs):
        super(TestRunFilterSubscriptionForm, self).__init__(*args, **kwargs)
        self.instance.filter = filter
        self.instance.user = user


@BreadCrumb("Manage Subscription", parent=filter_detail, needs=['name', 'username'])
@login_required
def filter_subscribe(request, username, name):
    filter = TestRunFilter.objects.get(owner__username=username, name=name)
    if not filter.public and filter.owner != request.user:
        raise PermissionDenied()
    try:
        subscription = TestRunFilterSubscription.objects.get(
            user=request.user, filter=filter)
    except TestRunFilterSubscription.DoesNotExist:
        subscription = None
    if request.method == "POST":
        form = TestRunFilterSubscriptionForm(
            filter, request.user, request.POST, instance=subscription)
        if form.is_valid():
            if 'unsubscribe' in request.POST:
                subscription.delete()
            else:
                form.save()
            return HttpResponseRedirect(filter.get_absolute_url())
    else:
        form = TestRunFilterSubscriptionForm(
            filter, request.user, instance=subscription)
    return render_to_response(
        'dashboard_app/filter_subscribe.html', {
            'filter': filter,
            'form': form,
            'subscription': subscription,
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                filter_subscribe, name=name, username=username),
        }, RequestContext(request)
    )


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
<script type="text/javascript" src="{{ STATIC_URL }}dashboard_app/js/filter-edit.js"></script>
'''


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

    test = forms.ModelChoiceField(
        queryset=Test.objects.order_by('test_id'), empty_label="<any>", required=False)

    test_case = forms.ModelChoiceField(
        queryset=TestCase.objects.none(), empty_label="<any>", required=False)

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
            for (name, value) in self.attributes:
                instance.attributes.create(name=name, value=value)
        return instance

    @property
    def summary_data(self):
        data = self.cleaned_data.copy()
        data['attributes'] = self.attributes
        return data

    def __init__(self, user, *args, **kwargs):
        super(TestRunFilterForm, self).__init__(*args, **kwargs)
        self.instance.owner = user
        self.fields['bundle_streams'].queryset = BundleStream.objects.accessible_by_principal(user)
        self.fields['name'].validators.append(self.validate_name)
        test = self['test'].value()
        if test:
            if not isinstance(test, int):
                test = int(repr(test)[2:-1])
            test = Test.objects.get(pk=test)
            self.fields['test_case'].queryset = TestCase.objects.filter(test=test).order_by('test_case_id')

    @property
    def attributes(self):
        if not self.is_bound and self.instance.pk:
            return self.instance.attributes.values_list('name', 'value')
        else:
            attributes = []
            for (var, value) in self.data.iteritems():
                if var.startswith('attribute_key_'):
                    index = int(var[len('attribute_key_'):])
                    attr_value = self.data['attribute_value_' + str(index)]
                    attributes.append((index, value, attr_value))

            attributes.sort()
            attributes = [a[1:] for a in attributes]
            return attributes

    def get_test_runs(self, user):
        assert self.is_valid(), self.errors
        filter = self.save(commit=False)
        return filter.get_test_runs_impl(
            user, self.cleaned_data['bundle_streams'], self.attributes)


def filter_form(request, bread_crumb_trail, instance=None):
    if request.method == 'POST':
        form = TestRunFilterForm(request.user, request.POST, instance=instance)

        if form.is_valid():
            if 'save' in request.POST:
                filter = form.save()
                return HttpResponseRedirect(filter.get_absolute_url())
            else:
                c = request.POST.copy()
                c.pop('csrfmiddlewaretoken', None)
                return render_to_response(
                    'dashboard_app/filter_preview.html', {
                        'bread_crumb_trail': bread_crumb_trail,
                        'form': form,
                        'table': FilterPreviewTable(
                            'filter-preview',
                            reverse(filter_preview_json) + '?' + c.urlencode(),
                            params=(request.user, form)),
                    }, RequestContext(request))
    else:
        form = TestRunFilterForm(request.user, instance=instance)
    return render_to_response(
        'dashboard_app/filter_add.html', {
            'bread_crumb_trail': bread_crumb_trail,
            'form': form,
        }, RequestContext(request))


@BreadCrumb("Add new filter", parent=filters_list)
def filter_add(request):
    return filter_form(
        request,
        BreadCrumbTrail.leading_to(filter_add))


@BreadCrumb("Edit", parent=filter_detail, needs=['name', 'username'])
def filter_edit(request, username, name):
    if request.user.username != username:
        raise PermissionDenied()
    filter = TestRunFilter.objects.get(owner=request.user, name=name)
    return filter_form(
        request,
        BreadCrumbTrail.leading_to(filter_edit, name=name, username=username),
        instance=filter)


@BreadCrumb("Delete", parent=filter_detail, needs=['name', 'username'])
def filter_delete(request, username, name):
    if request.user.username != username:
        raise PermissionDenied()
    filter = TestRunFilter.objects.get(owner=request.user, name=name)
    if request.method == "POST":
        if 'yes' in request.POST:
            filter.delete()
            return HttpResponseRedirect(reverse(filters_list))
        else:
            return HttpResponseRedirect(filter.get_absolute_url())
    return render_to_response(
        'dashboard_app/filter_delete.html', {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(filter_delete, name=name, username=username),
            'filter': filter,
        }, RequestContext(request))


def filter_add_cases_for_test_json(request):
    test = Test.objects.get(test_id=request.GET['test'])
    result = TestCase.objects.filter(test=test).order_by('test_case_id').values('test_case_id', 'id')
    return HttpResponse(
        json.dumps(list(result)),
        mimetype='application/json')


def filter_attr_name_completion_json(request):
    term = request.GET['term']
    result = NamedAttribute.objects.filter(
        name__startswith=term).distinct('name').order_by('name').values_list('name', flat=True)
    return HttpResponse(
        json.dumps(list(result)),
        mimetype='application/json')


def filter_attr_value_completion_json(request):
    name = request.GET['name']
    term = request.GET['term']
    result = NamedAttribute.objects.filter(
        name=name,
        value__startswith=term).distinct('value').order_by('value').values_list('value', flat=True)
    return HttpResponse(
        json.dumps(list(result)),
        mimetype='application/json')


def test_run_detail_test_json(request, pathname, content_sha1, analyzer_assigned_uuid):
    test_run = get_restricted_object_or_404(
        TestRun, lambda test_run: test_run.bundle.bundle_stream,
        request.user,
        analyzer_assigned_uuid=analyzer_assigned_uuid
        )
    return TestTable.json(request, params=(test_run,))


@BreadCrumb(
    "Run {analyzer_assigned_uuid}",
    parent=bundle_detail,
    needs=['pathname', 'content_sha1', 'analyzer_assigned_uuid'])
def test_run_detail(request, pathname, content_sha1, analyzer_assigned_uuid):
    test_run = get_restricted_object_or_404(
        TestRun,
        lambda test_run: test_run.bundle.bundle_stream,
        request.user,
        analyzer_assigned_uuid=analyzer_assigned_uuid
    )
    return render_to_response(
        "dashboard_app/test_run_detail.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                test_run_detail,
                pathname=pathname,
                content_sha1=content_sha1,
                analyzer_assigned_uuid=analyzer_assigned_uuid),
            "test_run": test_run,
            "test_table": TestTable(
                'test-table',
                reverse(test_run_detail_test_json, kwargs=dict(
                    pathname=pathname,
                    content_sha1=content_sha1,
                    analyzer_assigned_uuid=analyzer_assigned_uuid)),
                params=(test_run,))

        }, RequestContext(request))


@BreadCrumb(
    "Software Context",
    parent=test_run_detail,
    needs=['pathname', 'content_sha1', 'analyzer_assigned_uuid'])
def test_run_software_context(request, pathname, content_sha1, analyzer_assigned_uuid):
    test_run = get_restricted_object_or_404(
        TestRun,
        lambda test_run: test_run.bundle.bundle_stream,
        request.user,
        analyzer_assigned_uuid=analyzer_assigned_uuid
    )
    return render_to_response(
        "dashboard_app/test_run_software_context.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                test_run_software_context,
                pathname=pathname,
                content_sha1=content_sha1,
                analyzer_assigned_uuid=analyzer_assigned_uuid),
            "test_run": test_run
        }, RequestContext(request))


@BreadCrumb(
    "Hardware Context",
    parent=test_run_detail,
    needs=['pathname', 'content_sha1', 'analyzer_assigned_uuid'])
def test_run_hardware_context(request, pathname, content_sha1, analyzer_assigned_uuid):
    test_run = get_restricted_object_or_404(
        TestRun,
        lambda test_run: test_run.bundle.bundle_stream,
        request.user,
        analyzer_assigned_uuid=analyzer_assigned_uuid
    )
    return render_to_response(
        "dashboard_app/test_run_hardware_context.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                test_run_hardware_context,
                pathname=pathname,
                content_sha1=content_sha1,
                analyzer_assigned_uuid=analyzer_assigned_uuid),
            "test_run": test_run
        }, RequestContext(request))


@BreadCrumb(
    "Details of result {relative_index}",
    parent=test_run_detail,
    needs=['pathname', 'content_sha1', 'analyzer_assigned_uuid', 'relative_index'])
def test_result_detail(request, pathname, content_sha1, analyzer_assigned_uuid, relative_index):
    test_run = get_restricted_object_or_404(
        TestRun,
        lambda test_run: test_run.bundle.bundle_stream,
        request.user,
        analyzer_assigned_uuid=analyzer_assigned_uuid
    )
    test_result = test_run.test_results.get(relative_index=relative_index)
    return render_to_response(
        "dashboard_app/test_result_detail.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                test_result_detail,
                pathname=pathname,
                content_sha1=content_sha1,
                analyzer_assigned_uuid=analyzer_assigned_uuid,
                relative_index=relative_index),
            "test_result": test_result
        }, RequestContext(request))


@BreadCrumb(
    "Attachments",
    parent=test_run_detail,
    needs=['pathname', 'content_sha1', 'analyzer_assigned_uuid'])
def attachment_list(request, pathname, content_sha1, analyzer_assigned_uuid):
    test_run = get_restricted_object_or_404(
        TestRun,
        lambda test_run: test_run.bundle.bundle_stream,
        request.user,
        analyzer_assigned_uuid=analyzer_assigned_uuid
    )
    return object_list(
        request,
        queryset=test_run.attachments.all(),
        template_name="dashboard_app/attachment_list.html",
        template_object_name="attachment",
        extra_context={
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                attachment_list,
                pathname=pathname,
                content_sha1=content_sha1,
                analyzer_assigned_uuid=analyzer_assigned_uuid),
            'test_run': test_run})


@BreadCrumb(
    "{content_filename}",
    parent=attachment_list,
    needs=['pathname', 'content_sha1', 'analyzer_assigned_uuid', 'pk'])
def attachment_detail(request, pathname, content_sha1, analyzer_assigned_uuid, pk):
    attachment = get_restricted_object_or_404(
        Attachment,
        lambda attachment: attachment.test_run.bundle.bundle_stream,
        request.user,
        pk = pk
    )
    return render_to_response(
        "dashboard_app/attachment_detail.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                attachment_detail,
                pathname=pathname,
                content_sha1=content_sha1,
                analyzer_assigned_uuid=analyzer_assigned_uuid,
                pk=pk,
                content_filename=attachment.content_filename),
            "attachment": attachment,
        }, RequestContext(request))


def ajax_attachment_viewer(request, pk):
    attachment = get_restricted_object_or_404(
        Attachment,
        lambda attachment: attachment.test_run.bundle.bundle_stream,
        request.user,
        pk=pk
    )
    data = attachment.get_content_if_possible(
        mirror=request.user.is_authenticated())
    if attachment.mime_type == "text/plain":
        return render_to_response(
            "dashboard_app/_ajax_attachment_viewer.html", {
                "attachment": attachment,
                "lines": data.splitlines() if data else None,
            },
            RequestContext(request))
    else:
        response = HttpResponse(mimetype=attachment.mime_type)
        response['Content-Disposition'] = 'attachment; filename=%s' % (
                                           attachment.content_filename)
        response.write(data)
        return response


@BreadCrumb("Reports", parent=index)
def report_list(request):
    return render_to_response(
        "dashboard_app/report_list.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(report_list),
            "report_list": DataReport.repository.all()
        }, RequestContext(request))


@BreadCrumb("{title}", parent=report_list, needs=['name'])
def report_detail(request, name):
    try:
        report = DataReport.repository.get(name=name)
    except DataReport.DoesNotExist:
        raise Http404('No report matches given name.')
    return render_to_response(
        "dashboard_app/report_detail.html", {
            "is_iframe": request.GET.get("iframe") == "yes",
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                report_detail,
                name=report.name,
                title=report.title),
            "report": report,
        }, RequestContext(request))


@BreadCrumb("Data views", parent=index)
def data_view_list(request):
    return render_to_response(
        "dashboard_app/data_view_list.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(data_view_list),
            "data_view_list": DataView.repository.all(),
        }, RequestContext(request))


@BreadCrumb(
    "Details of {name}",
    parent=data_view_list,
    needs=['name'])
def data_view_detail(request, name):
    try:
        data_view = DataView.repository.get(name=name)
    except DataView.DoesNotExist:
        raise Http404('No data view matches the given query.')
    return render_to_response(
        "dashboard_app/data_view_detail.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                data_view_detail,
                name=data_view.name,
                summary=data_view.summary),
            "data_view": data_view
        }, RequestContext(request))


@BreadCrumb("Tests", parent=index)
def test_list(request):
    return object_list(
        request,
        queryset=Test.objects.all(),
        template_name="dashboard_app/test_list.html",
        template_object_name="test",
        extra_context={
            'bread_crumb_trail': BreadCrumbTrail.leading_to(test_list)
        })


@BreadCrumb("Details of {test_id}", parent=test_list, needs=['test_id'])
def test_detail(request, test_id):
    return object_detail(
        request,
        queryset=Test.objects.all(),
        slug=test_id,
        slug_field="test_id",
        template_name="dashboard_app/test_detail.html",
        template_object_name="test",
        extra_context={
            'bread_crumb_trail': BreadCrumbTrail.leading_to(test_detail, test_id=test_id)
        })


def redirect_to(request, object, trailing):
    url = object.get_absolute_url() + trailing
    qs = request.META.get('QUERY_STRING')
    if qs:
        url += '?' + qs
    return redirect(url)


def redirect_to_test_run(request, analyzer_assigned_uuid, trailing=''):
    test_run = get_restricted_object_or_404(
        TestRun,
        lambda test_run: test_run.bundle.bundle_stream,
        request.user,
        analyzer_assigned_uuid=analyzer_assigned_uuid)
    return redirect_to(request, test_run, trailing)


def redirect_to_test_result(request, analyzer_assigned_uuid, relative_index,
                            trailing=''):
    test_result = get_restricted_object_or_404(
        TestResult,
        lambda test_result: test_result.test_run.bundle.bundle_stream,
        request.user,
        test_run__analyzer_assigned_uuid=analyzer_assigned_uuid,
        relative_index=relative_index)
    return redirect_to(request, test_result, trailing)


def redirect_to_bundle(request, content_sha1, trailing=''):
    bundle = get_restricted_object_or_404(
        Bundle,
        lambda bundle: bundle.bundle_stream,
        request.user,
        content_sha1=content_sha1)
    return redirect_to(request, bundle, trailing)


@BreadCrumb("Testing efforts", parent=index)
def testing_effort_list(request):
    return render_to_response(
        "dashboard_app/testing_effort_list.html", {
            'effort_list': TestingEffort.objects.all(
            ).order_by('name'),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                testing_effort_list),
        }, RequestContext(request))


@BreadCrumb(
    "{effort}",
    parent=testing_effort_list,
    needs=["pk"])
def testing_effort_detail(request, pk):
    effort = get_object_or_404(TestingEffort, pk=pk)
    return render_to_response(
        "dashboard_app/testing_effort_detail.html", {
            'effort': effort,
            'belongs_to_user': effort.project.is_owned_by(request.user),
            'test_run_list': effort.get_test_runs(
            ).select_related(
                'denormalization',
                'bundle',
                'bundle__bundle_stream',
                'test',
            ),
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                testing_effort_detail,
                effort=effort,
                pk=pk),
        }, RequestContext(request))


from lava_projects.models import Project
from lava_projects.views import project_detail
from dashboard_app.forms import TestingEffortForm


@BreadCrumb(
    "Start a new test effort",
    parent=project_detail,
    needs=["project_identifier"])
@login_required
def testing_effort_create(request, project_identifier):
    project = get_object_or_404(Project, identifier=project_identifier)
    if request.method == 'POST':
        form = TestingEffortForm(request.POST)
        # Check the form
        if form.is_valid():
            # And make a project instance
            effort = TestingEffort.objects.create(
                name=form.cleaned_data['name'],
                description=form.cleaned_data['description'],
                project=project)
            # Create all the required tags
            effort.tags = [
                Tag.objects.get_or_create(name=tag_name)[0]
                for tag_name in re.split("[, ]+", form.cleaned_data["tags"])
                if tag_name != ""]
            return HttpResponseRedirect(effort.get_absolute_url())
    else:
        form = TestingEffortForm()
    # Render to template
    template_name = "dashboard_app/testing_effort_form.html"
    t = loader.get_template(template_name)
    c = RequestContext(request, {
        'form': form,
        'bread_crumb_trail': BreadCrumbTrail.leading_to(
            testing_effort_create,
            project=project,
            project_identifier=project.identifier)
    })
    return HttpResponse(t.render(c))


@BreadCrumb(
    "Update",
    parent=testing_effort_detail,
    needs=["pk"])
@login_required
def testing_effort_update(request, pk):
    try:
        effort = TestingEffort.objects.get(pk=pk)
    except TestingEffort.DoesNotExist:
        raise Http404()
    if not effort.project.is_owned_by(request.user):
        return HttpResponse("not allowed")
    if request.method == 'POST':
        form = TestingEffortForm(request.POST)
        # Check the form
        if form.is_valid():
            # And update the effort object
            effort.name=form.cleaned_data['name']
            effort.description=form.cleaned_data['description']
            # As well as tags
            effort.tags = [
                Tag.objects.get_or_create(name=tag_name)[0]
                for tag_name in re.split("[, ]+", form.cleaned_data["tags"])
                if tag_name != ""]
            # Save the changes
            effort.save()
            return HttpResponseRedirect(effort.get_absolute_url())
    else:
        form = TestingEffortForm(initial={
            'name': effort.name,
            'description': effort.description,
            'tags': " ".join([tag.name for tag in effort.tags.order_by('name').all()])
        })
    # Render to template
    template_name = "dashboard_app/testing_effort_form.html"
    t = loader.get_template(template_name)
    c = RequestContext(request, {
        'form': form,
        'effort': effort,
        'bread_crumb_trail': BreadCrumbTrail.leading_to(
            testing_effort_update,
            effort=effort,
            pk=effort.pk)
    })
    return HttpResponse(t.render(c))


@BreadCrumb("Image Reports", parent=index)
def image_report_list(request):
    imagesets = ImageSet.objects.all()
    imagesets_data = []
    for imageset in imagesets:
        images_data = []
        for image in imageset.images.all():
            image_data = {
                'name': image.name,
                'bundle_count': image.get_bundles(request.user).count(),
                'link': image.get_absolute_url(),
                }
            images_data.append(image_data)
        images_data.sort(key=lambda d:d['name'])
        imageset_data = {
            'name': imageset.name,
            'images': images_data,
            }
        imagesets_data.append(imageset_data)
    imagesets_data.sort(key=lambda d:d['name'])
    return render_to_response(
        "dashboard_app/image-reports.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(image_report_list),
            'imagesets': imagesets_data,
        }, RequestContext(request))


@BreadCrumb("{name}", parent=image_report_list, needs=['name'])
def image_report_detail(request, name):

    image = Image.objects.get(name=name)

    # We are aiming to produce a table like this:

    # Build Number | 23         | ... | 40         |
    # Date         | YYYY-MM-DD | ... | YYYY-MM-DD |
    # lava         | 1/3        | ... | 4/5        |
    # cts          | 100/100    | ... | 88/100     |
    # ...          | ...        | ... | ...        |
    # skia         | 1/2        | ... | 3/3        |

    # Data processing proceeds in 3 steps:

    # 1) Get the bundles/builds.  Image.get_latest_bundles() does the hard
    # work here and then we just peel off the data we need from the bundles.

    # 2) Get all the test runs we are interested in, extract the data we
    # need from them and associate them with the corresponding bundles.

    # 3) Organize the data so that it's natural for rendering the table
    # (basically transposing it from being bundle -> testrun -> result to
    # testrun -> bundle -> result).

    bundles = image.get_latest_bundles(request.user, 50)

    bundle_id_to_data = {}
    for bundle in bundles:
        bundle_id_to_data[bundle.id] = dict(
            number=bundle.build_number,
            date=bundle.uploaded_on,
            test_runs={},
            link=bundle.get_permalink(),
            )

    test_runs = TestRun.objects.filter(
        bundle__id__in=list(bundle_id_to_data),
        ).select_related(
        'bundle', 'denormalization', 'test').prefetch_related(
        'launchpad_bugs')

    test_run_names = set()
    for test_run in test_runs:
        name = test_run.test.test_id
        denorm = test_run.denormalization
        if denorm.count_pass == denorm.count_all():
            cls = 'present pass'
        else:
            cls = 'present fail'
        bug_ids = sorted([b.bug_id for b in test_run.launchpad_bugs.all()])
        test_run_data = dict(
            present=True,
            cls=cls,
            uuid=test_run.analyzer_assigned_uuid,
            passes=denorm.count_pass,
            total=denorm.count_all(),
            link=test_run.get_permalink(),
            bug_ids=bug_ids,
            )
        bundle_id_to_data[test_run.bundle.id]['test_runs'][name] = test_run_data
        if name != 'lava':
            test_run_names.add(name)

    test_run_names = sorted(test_run_names)
    test_run_names.insert(0, 'lava')

    bundles = sorted(bundle_id_to_data.values(), key=lambda d:d['number'])

    table_data = []

    for test_run_name in test_run_names:
        row_data = []
        for bundle in bundles:
            test_run_data = bundle['test_runs'].get(test_run_name)
            if not test_run_data:
                test_run_data = dict(
                    present=False,
                    cls='missing',
                    )
            row_data.append(test_run_data)
        table_data.append(row_data)

    return render_to_response(
        "dashboard_app/image-report.html", {
            'bread_crumb_trail': BreadCrumbTrail.leading_to(
                image_report_detail, name=image.name),
            'image': image,
            'bundles': bundles,
            'table_data': table_data,
            'test_run_names': test_run_names,
        }, RequestContext(request))


@require_POST
def link_bug_to_testrun(request):
    testrun = get_object_or_404(TestRun, analyzer_assigned_uuid=request.POST['uuid'])
    bug_id = request.POST['bug']
    lpbug = LaunchpadBug.objects.get_or_create(bug_id=int(bug_id))[0]
    testrun.launchpad_bugs.add(lpbug)
    testrun.save()
    return HttpResponseRedirect(request.POST['back'])


@require_POST
def unlink_bug_and_testrun(request):
    testrun = get_object_or_404(TestRun, analyzer_assigned_uuid=request.POST['uuid'])
    bug_id = request.POST['bug']
    lpbug = LaunchpadBug.objects.get_or_create(bug_id=int(bug_id))[0]
    testrun.launchpad_bugs.remove(lpbug)
    testrun.save()
    return HttpResponseRedirect(request.POST['back'])
