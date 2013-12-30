from django.conf import settings
from django.template import defaultfilters as filters
from django.utils.safestring import mark_safe
from django.utils.html import escape
import django_tables2 as tables
from django_tables2 import SingleTableView
from lava.utils.lavatable import LavaTable
from dashboard_app.models import (
    Attachment,
    Bundle,
    BundleStream,
    DataReport,
    DataView,
    Tag,
    Test,
    TestResult,
    TestRun,
    TestDefinition,
)


class BundleStreamTable(LavaTable):
    """
    List of bundle streams
    """

    def __init__(self, *args, **kwargs):
        super(BundleStreamTable, self).__init__(*args, **kwargs)
        self.length = 25

    pathname = tables.TemplateColumn(
        '<a href="{% url dashboard_app.views.bundle_list record.pathname %}">'
        '<code>{{ record.pathname }}</code></a>')
    name = tables.TemplateColumn(
        '{{ record.name|default:"<i>not set</i>" }}')
    number_of_test_runs = tables.TemplateColumn(
        '<a href="{% url dashboard_app.views.test_run_list record.pathname %}">'
        '{{ record.get_test_run_count }}')
    number_of_test_runs.orderable = False
    number_of_bundles = tables.TemplateColumn(
        '<a href="{% url dashboard_app.views.bundle_list record.pathname %}">'
        '{{ record.bundles.count}}</a>')
    number_of_bundles.orderable = False

    class Meta(LavaTable.Meta):
        searches = {
            'pathname': 'contains',
            'name': 'contains'
        }


class BundleTable(LavaTable):
    """
    List of bundles in a specified bundle stream.
    """

    def __init__(self, *args, **kwargs):
        super(BundleTable, self).__init__(*args, **kwargs)
        self.length = 25

    content_filename = tables.TemplateColumn(
        '<a href="{{ record.get_absolute_url }}">'
        '<code>{{ record.content_filename }}</code></a>',
        verbose_name="bundle name")

    passes = tables.TemplateColumn('{{ record.get_summary_results.pass|default:"0" }}')
    passes.orderable = False
    fails = tables.TemplateColumn('{{ record.get_summary_results.fail|default:"0" }}')
    fails.orderable = False
    total_results = tables.TemplateColumn('{{ record.get_summary_results.total }}')
    total_results.orderable = False

    uploaded_on = tables.TemplateColumn('{{ record.uploaded_on|date:"Y-m-d H:i:s"}}')
    uploaded_by = tables.TemplateColumn('''
        {% load i18n %}
        {% if record.uploaded_by %}
            {{ record.uploaded_by }}
        {% else %}
            <em>{% trans "anonymous user" %}</em>
        {% endif %}''')
    deserializaled = tables.TemplateColumn('{{ record.is_deserialized|yesno }}')
    deserializaled.orderable = False

    class Meta(LavaTable.Meta):
        searches = {
            'content_filename': 'contains',
        }


class BundleDetailTable(LavaTable):
    """
    Detail about a bundle from a particular stream
    """

    device = tables.Column(accessor='test_id')
    device.orderable = False
    test_run = tables.Column(accessor='test_id')
    test_run.orderable = False
    test = tables.Column()
    passes = tables.TemplateColumn('{{ record.get_summary_results.pass|default:"0" }}')
    passes.orderable = False
    fails = tables.TemplateColumn('{{ record.get_summary_results.fail|default:"0" }}')
    fails.orderable = False
    uploaded_on = tables.TemplateColumn('{{ record.bundle.uploaded_on|date:"Y-m-d H:i:s"}}')
    uploaded_on.orderable = False
    analyzed_on = tables.TemplateColumn('{{ record.analyzer_assigned_date|date:"Y-m-d H:i:s" }}')
    analyzed_on.orderable = False

    def render_device(self, record):
        return record.show_device()

    def render_test_run(self, record):
        return mark_safe('<a href="%s"><code>%s results<code/></a>' % (record.get_absolute_url(), record.test))

    class Meta(LavaTable.Meta):
        model = TestRun
        fields = (
            'device', 'test_run', 'test', 'passes',
            'fails', 'uploaded_on', 'analyzed_on'
        )
        sequence = fields
        searches = {}
        queries = {
            'test_run_query': 'test',
        }


class TestRunTable(LavaTable):
    """
    TAble of test runs in a specified bundle in a bundle stream.
    """

    record = tables.TemplateColumn(
        '<a href="{{ record.get_absolute_url }}">'
        '<code>{{ record.test }} results<code/></a>',
    )
    record.orderable = False

    test = tables.TemplateColumn(
        '<a href="{{ record.test.get_absolute_url }}">{{ record.test }}</a>',
    )

    uploaded_on = tables.TemplateColumn(
        '{{ record.bundle.uploaded_on|date:"Y-m-d H:i:s" }}',
    )
    uploaded_on.orderable = False

    analyzed_on = tables.TemplateColumn(
        '{{ record.analyzer_assigned_date|date:"Y-m-d H:i:s" }}',
    )
    analyzed_on.orderable = False

    class Meta(LavaTable.Meta):
        model = TestRun
        fields = (
            'record', 'test', 'uploaded_on', 'analyzed_on'
        )
        sequence = (
            'record', 'test', 'uploaded_on', 'analyzed_on'
        )
        searches = {
        }
        queries = {
            'test_run_query': 'test'
        }


class TestTable(LavaTable):

    def __init__(self, request, *args, **kwargs):
        super(TestTable, self).__init__(request, *args, **kwargs)
        self.length = 25

    relative_index = tables.Column(
        verbose_name="#",
        attrs={"th": {"style": "width: 1%"}},
        default=mark_safe("<em>Not specified</em>"))

    test_case = tables.Column()

    result = tables.TemplateColumn('''
        <a href="{{record.get_absolute_url}}">
          <img src="{{ STATIC_URL }}dashboard_app/images/icon-{{ record.result_code }}.png"
          alt="{{ record.result_code }}" width="16" height="16" border="0"/>{{ record.result_code }}
        {% if record.attachments__count %}
        <a href="{{record.get_absolute_url}}#attachments">
          <img style="float:right;" src="{{ STATIC_URL }}dashboard_app/images/attachment.png"
               alt="This result has {{ record.attachments__count }} attachments"
               title="This result has {{ record.attachments__count }} attachments"
               /></a>
        {% endif %}
        ''')

    measurement = tables.TemplateColumn(
        '{{ record.measurement|default_if_none:"Not specified" }} {{ record.units }}',
        verbose_name="measurement")

    comments = tables.TemplateColumn('''
    {{ record.comments|default_if_none:"Not specified"|truncatewords:7 }}
    ''')

    class Meta(LavaTable.Meta):
        model = TestResult
        fields = (
            'relative_index', 'test_case', 'result',
            'measurement', 'comments',
        )
        sequence = fields
        searches = {
            'comments': 'contains',
        }
        queries = {
            'results_query': 'result',
            'test_case_query': 'test_case',
        }


class TestDefinitionTable(LavaTable):
    name = tables.Column()
    version = tables.Column()
    location = tables.Column()
    description = tables.Column()

    class Meta(LavaTable.Meta):
        pass
