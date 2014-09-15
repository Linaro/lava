# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
import dashboard_app.models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Attachment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('content', models.FileField(help_text='Attachment content', upload_to=b'attachments', null=True, verbose_name='Content')),
                ('content_filename', models.CharField(help_text='Name of the original attachment', max_length=256, verbose_name='Content file name')),
                ('mime_type', models.CharField(max_length=64, verbose_name='MIME type')),
                ('public_url', models.URLField(max_length=512, verbose_name='Public URL', blank=True)),
                ('object_id', models.PositiveIntegerField()),
                ('content_type', models.ForeignKey(to='contenttypes.ContentType')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='BugLink',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('bug_link', models.CharField(help_text='Maximum length: 1024 characters', max_length=1024, verbose_name='Bug Link', blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Bundle',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uploaded_on', models.DateTimeField(default=datetime.datetime.utcnow, verbose_name='Uploaded on', editable=False)),
                ('is_deserialized', models.BooleanField(help_text='Set when document has been analyzed and loaded into the database', verbose_name='Is deserialized', editable=False)),
                ('_raw_content', models.FileField(help_text='Document in Dashboard Bundle Format 1.0', upload_to=b'bundles', null=True, verbose_name='Content', db_column=b'content')),
                ('_gz_content', models.FileField(db_column=b'gz_content', storage=dashboard_app.models.GzipFileSystemStorage(), upload_to=b'compressed-bundles', help_text='Compressed document in Dashboard Bundle Format 1.0', null=True, verbose_name='Compressed content')),
                ('content_sha1', models.CharField(max_length=40, unique=True, null=True, editable=False)),
                ('content_filename', models.CharField(help_text='Name of the originally uploaded bundle', max_length=256, verbose_name='Content file name')),
            ],
            options={
                'ordering': ['-uploaded_on'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='BundleDeserializationError',
            fields=[
                ('bundle', models.OneToOneField(related_name=b'deserialization_error', primary_key=True, serialize=False, to='dashboard_app.Bundle')),
                ('error_message', models.CharField(max_length=1024)),
                ('traceback', models.TextField(max_length=32768)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='BundleStream',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('is_public', models.BooleanField(default=False)),
                ('slug', models.CharField(help_text='Name that you will use when uploading bundles. Maximum length: 64 characters', max_length=64, verbose_name='Slug', blank=True)),
                ('name', models.CharField(help_text='Maximum length: 64 characters', max_length=64, verbose_name='Name', blank=True)),
                ('pathname', models.CharField(unique=True, max_length=128, editable=False)),
                ('is_anonymous', models.BooleanField()),
                ('group', models.ForeignKey(blank=True, to='auth.Group', null=True)),
                ('user', models.ForeignKey(blank=True, to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='HardwareDevice',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('device_type', models.CharField(help_text='One of pre-defined device types', max_length=32, verbose_name='Device Type', choices=[('device.cpu', 'CPU'), ('device.mem', 'Memory'), ('device.usb', 'USB device'), ('device.pci', 'PCI device'), ('device.board', 'Board/Motherboard')])),
                ('description', models.CharField(help_text='Human readable device summary. Maximum length: 256 characters', max_length=256, verbose_name='Description')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Image',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.SlugField(unique=True, max_length=1024)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ImageChartFilter',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('representation', models.CharField(default=b'lines', max_length=20, verbose_name=b'Representation', choices=[(b'lines', b'Lines'), (b'bars', b'Bars')])),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ImageChartTest',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=200)),
                ('image_chart_filter', models.ForeignKey(to='dashboard_app.ImageChartFilter')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ImageChartTestAttribute',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.TextField()),
                ('image_chart_test', models.ForeignKey(to='dashboard_app.ImageChartTest')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ImageChartTestCase',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=200)),
                ('image_chart_filter', models.ForeignKey(to='dashboard_app.ImageChartFilter')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ImageChartTestCaseAttribute',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.TextField()),
                ('image_chart_test_case', models.ForeignKey(to='dashboard_app.ImageChartTestCase')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ImageChartTestCaseUser',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('is_visible', models.BooleanField(default=True, verbose_name=b'Visible')),
                ('image_chart_test_case', models.ForeignKey(to='dashboard_app.ImageChartTestCase')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ImageChartTestUser',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('is_visible', models.BooleanField(default=True, verbose_name=b'Visible')),
                ('image_chart_test', models.ForeignKey(to='dashboard_app.ImageChartTest')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ImageChartUser',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('start_date', models.CharField(max_length=20)),
                ('is_legend_visible', models.BooleanField(default=True, verbose_name=b'Toggle legend')),
                ('has_subscription', models.BooleanField(default=False, verbose_name=b'Subscribed to target goal')),
                ('toggle_percentage', models.BooleanField(default=False, verbose_name=b'Toggle percentage')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ImageReport',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.SlugField(unique=True, max_length=1024)),
                ('description', models.TextField(null=True, blank=True)),
                ('is_published', models.BooleanField(default=False, verbose_name=b'Published')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ImageReportChart',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(null=True, blank=True)),
                ('chart_type', models.CharField(default=b'pass/fail', max_length=20, verbose_name=b'Chart type', choices=[(b'pass/fail', b'Pass/Fail'), (b'measurement', b'Measurement')])),
                ('target_goal', models.DecimalField(null=True, verbose_name=b'Target goal', max_digits=10, decimal_places=5, blank=True)),
                ('is_interactive', models.BooleanField(default=False, verbose_name=b'Interactive')),
                ('is_data_table_visible', models.BooleanField(default=False, verbose_name=b'Data table visible')),
                ('image_report', models.ForeignKey(default=None, to='dashboard_app.ImageReport')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ImageReportGroup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.SlugField(unique=True, max_length=1024)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ImageSet',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=1024)),
                ('images', models.ManyToManyField(to='dashboard_app.Image')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='NamedAttribute',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.TextField()),
                ('value', models.TextField()),
                ('object_id', models.PositiveIntegerField()),
                ('content_type', models.ForeignKey(to='contenttypes.ContentType')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='PMQABundleStream',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('bundle_stream', models.ForeignKey(related_name=b'+', to='dashboard_app.BundleStream')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SoftwarePackage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(help_text='Maximum length: 128 characters', max_length=128, verbose_name='Package name')),
                ('version', models.CharField(help_text='Maximum length: 128 characters', max_length=128, verbose_name='Package version')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SoftwarePackageScratch',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128)),
                ('version', models.CharField(max_length=128)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SoftwareSource',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('project_name', models.CharField(help_text='Maximum length: 32 characters', max_length=32, verbose_name='Project Name')),
                ('branch_url', models.CharField(help_text='Maximum length: 256 characters', max_length=256, verbose_name='Branch URL')),
                ('branch_vcs', models.CharField(help_text='Maximum length: 10 characters', max_length=10, verbose_name='Branch VCS')),
                ('branch_revision', models.CharField(help_text='Maximum length: 128 characters', max_length=128, verbose_name='Branch Revision')),
                ('commit_timestamp', models.DateTimeField(help_text='Date and time of the commit (optional)', null=True, verbose_name='Commit Timestamp', blank=True)),
                ('default_params', models.CharField(help_text=b'Default parameters for lava-test-shell.', max_length=1024, null=True, verbose_name='Default parameters', blank=True)),
                ('test_params', models.CharField(help_text=b'Runtime test parameters for lava-test-shell.', max_length=1024, null=True, verbose_name='Test parameters', blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.SlugField(unique=True, max_length=256, verbose_name='Tag')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Test',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('test_id', models.CharField(unique=True, max_length=1024, verbose_name='Test ID')),
                ('name', models.CharField(max_length=1024, verbose_name='Name', blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TestCase',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('test_case_id', models.TextField(verbose_name='Test case ID')),
                ('name', models.TextField(help_text='Maximum length: 100 characters', verbose_name='Name', blank=True)),
                ('units', models.TextField(help_text='Units in which measurement value should be\n                     interpreted in, for example <q>ms</q>, <q>MB/s</q> etc.\n                     There is no semantical meaning inferred from the value of\n                     this field, free form text is allowed. <br/>Maximum length: 100 characters', verbose_name='Units', blank=True)),
                ('test', models.ForeignKey(related_name=b'test_cases', to='dashboard_app.Test')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TestDefinition',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(help_text='Maximum length: 512 characters', unique=True, max_length=512, verbose_name='Name')),
                ('version', models.CharField(help_text='Maximum length: 256 characters', max_length=256, verbose_name='Version')),
                ('description', models.TextField(verbose_name='Description')),
                ('format', models.CharField(help_text='Maximum length: 128 characters', max_length=128, verbose_name='Format')),
                ('location', models.CharField(default=b'LOCAL', max_length=64, verbose_name='Location', choices=[(b'LOCAL', b'Local'), (b'URL', b'URL'), (b'GIT', b'GIT Repo'), (b'BZR', b'BZR Repo')])),
                ('url', models.CharField(help_text='Maximum length: 1024 characters', max_length=1024, verbose_name='URL')),
                ('environment', models.CharField(help_text='Maximum length: 256 characters', max_length=256, verbose_name='Environment')),
                ('target_os', models.CharField(help_text='Maximum length: 512 characters', max_length=512, verbose_name='Operating Systems')),
                ('target_dev_types', models.CharField(help_text='Maximum length: 512 characters', max_length=512, verbose_name='Device types')),
                ('content', models.FileField(help_text='Test definition file', upload_to=b'testdef', null=True, verbose_name='Upload Test Definition', blank=True)),
                ('mime_type', models.CharField(default=b'text/plain', help_text='Maximum length: 64 characters', max_length=64, verbose_name='MIME type')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TestResult',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('result', models.PositiveSmallIntegerField(help_text='Result classification to pass/fail group', verbose_name='Result', choices=[(0, 'Test passed'), (1, 'Test failed'), (2, 'Test skipped'), (3, 'Unknown outcome')])),
                ('measurement', models.DecimalField(decimal_places=10, max_digits=20, blank=True, help_text='Arbitrary value that was measured as a part of this test.', null=True, verbose_name='Measurement')),
                ('filename', models.CharField(max_length=1024, null=True, blank=True)),
                ('lineno', models.PositiveIntegerField(null=True, blank=True)),
                ('message', models.TextField(max_length=1024, null=True, blank=True)),
                ('microseconds', models.BigIntegerField(null=True, blank=True)),
                ('timestamp', models.DateTimeField(null=True, blank=True)),
                ('relative_index', models.PositiveIntegerField(help_text='The relative order of test results in one test run')),
                ('comments', models.TextField(null=True, blank=True)),
                ('test_case', models.ForeignKey(related_name=b'test_results', blank=True, to='dashboard_app.TestCase', null=True)),
            ],
            options={
                'ordering': ['relative_index'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TestRun',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('analyzer_assigned_uuid', models.CharField(help_text='You can use uuid.uuid1() to generate a value', unique=True, max_length=36, verbose_name='Analyzer assigned UUID')),
                ('analyzer_assigned_date', models.DateTimeField(help_text='Time stamp when the log was processed by the log analyzer', verbose_name='Analyzer assigned date')),
                ('import_assigned_date', models.DateTimeField(help_text='Time stamp when the bundle was imported', verbose_name='Import assigned date', auto_now_add=True)),
                ('time_check_performed', models.BooleanField(help_text="Indicator on wether timestamps in the log file (and any data derived from them) should be trusted.<br/>Many pre-production or development devices do not have a battery-powered RTC and it's not common for development images not to synchronize time with internet time servers.<br/>This field allows us to track tests results that <em>certainly</em> have correct time if we ever end up with lots of tests results from 1972", verbose_name='Time check performed')),
                ('microseconds', models.BigIntegerField(null=True, blank=True)),
                ('sw_image_desc', models.CharField(max_length=100, verbose_name='Operating System Image', blank=True)),
            ],
            options={
                'ordering': ['-import_assigned_date'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TestRunDenormalization',
            fields=[
                ('test_run', models.OneToOneField(related_name=b'denormalization', primary_key=True, serialize=False, to='dashboard_app.TestRun')),
                ('count_pass', models.PositiveIntegerField()),
                ('count_fail', models.PositiveIntegerField()),
                ('count_skip', models.PositiveIntegerField()),
                ('count_unknown', models.PositiveIntegerField()),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TestRunFilter',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.SlugField(help_text=b'The <b>name</b> of a filter is used to refer to it in the web UI and in email notifications triggered by this filter.', max_length=1024)),
                ('public', models.BooleanField(default=False, help_text=b'Whether other users can see this filter.')),
                ('build_number_attribute', models.CharField(help_text=b'For some filters, there is a natural <b>build number</b>.  If you specify the name of the attribute that contains the build number here, the results of the filter will be grouped and ordered by this build number.', max_length=1024, null=True, blank=True)),
                ('bundle_streams', models.ManyToManyField(help_text=b'A filter only matches tests within the given <b>bundle streams</b>.', to='dashboard_app.BundleStream')),
                ('owner', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
                ('uploaded_by', models.ForeignKey(related_name=b'+', blank=True, to=settings.AUTH_USER_MODEL, help_text=b'Only consider bundles uploaded by this user', null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TestRunFilterAttribute',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=1024)),
                ('value', models.CharField(max_length=1024)),
                ('filter', models.ForeignKey(related_name=b'attributes', to='dashboard_app.TestRunFilter')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TestRunFilterSubscription',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('level', models.IntegerField(default=0, help_text=b'You can choose to be <b>notified by email</b>:<ul><li>whenever a test that matches the criteria of this filter is executed</li><li>only when a test that matches the criteria of this filter fails</ul>', choices=[(0, b'Only when failed'), (1, b'Always')])),
                ('filter', models.ForeignKey(to='dashboard_app.TestRunFilter')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TestRunFilterTest',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('index', models.PositiveIntegerField(help_text='The index of this test in the filter')),
                ('filter', models.ForeignKey(related_name=b'tests', to='dashboard_app.TestRunFilter')),
                ('test', models.ForeignKey(related_name=b'+', to='dashboard_app.Test')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TestRunFilterTestCase',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('index', models.PositiveIntegerField(help_text='The index of this case in the test')),
                ('test', models.ForeignKey(related_name=b'cases', to='dashboard_app.TestRunFilterTest')),
                ('test_case', models.ForeignKey(related_name=b'+', to='dashboard_app.TestCase')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='testrunfiltersubscription',
            unique_together=set([('user', 'filter')]),
        ),
        migrations.AlterUniqueTogether(
            name='testrunfilter',
            unique_together=set([('owner', 'name')]),
        ),
        migrations.AddField(
            model_name='testrun',
            name='bundle',
            field=models.ForeignKey(related_name=b'test_runs', to='dashboard_app.Bundle'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='testrun',
            name='devices',
            field=models.ManyToManyField(related_name=b'test_runs', verbose_name='Hardware devices', to='dashboard_app.HardwareDevice', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='testrun',
            name='packages',
            field=models.ManyToManyField(related_name=b'test_runs', verbose_name='Software packages', to='dashboard_app.SoftwarePackage', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='testrun',
            name='sources',
            field=models.ManyToManyField(related_name=b'test_runs', verbose_name='Software sources', to='dashboard_app.SoftwareSource', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='testrun',
            name='tags',
            field=models.ManyToManyField(related_name=b'test_runs', verbose_name='Tags', to='dashboard_app.Tag', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='testrun',
            name='test',
            field=models.ForeignKey(related_name=b'test_runs', to='dashboard_app.Test'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='testresult',
            name='test_run',
            field=models.ForeignKey(related_name=b'test_results', to='dashboard_app.TestRun'),
            preserve_default=True,
        ),
        migrations.AlterOrderWithRespectTo(
            name='testresult',
            order_with_respect_to='test_run',
        ),
        migrations.AlterUniqueTogether(
            name='testcase',
            unique_together=set([('test', 'test_case_id')]),
        ),
        migrations.AlterUniqueTogether(
            name='softwarepackage',
            unique_together=set([('name', 'version')]),
        ),
        migrations.AlterUniqueTogether(
            name='namedattribute',
            unique_together=set([('object_id', 'name')]),
        ),
        migrations.AlterUniqueTogether(
            name='imagereportchart',
            unique_together=set([('image_report', 'name')]),
        ),
        migrations.AddField(
            model_name='imagereport',
            name='image_report_group',
            field=models.ForeignKey(default=None, to='dashboard_app.ImageReportGroup', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='imagereport',
            name='user',
            field=models.ForeignKey(default=None, to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='imagechartuser',
            name='image_chart',
            field=models.ForeignKey(to='dashboard_app.ImageReportChart'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='imagechartuser',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='imagechartuser',
            unique_together=set([('image_chart', 'user')]),
        ),
        migrations.AlterUniqueTogether(
            name='imagecharttestuser',
            unique_together=set([('image_chart_test', 'user')]),
        ),
        migrations.AlterUniqueTogether(
            name='imagecharttestcaseuser',
            unique_together=set([('image_chart_test_case', 'user')]),
        ),
        migrations.AddField(
            model_name='imagecharttestcase',
            name='test_case',
            field=models.ForeignKey(to='dashboard_app.TestCase'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='imagecharttestcase',
            unique_together=set([('image_chart_filter', 'test_case')]),
        ),
        migrations.AddField(
            model_name='imagecharttest',
            name='test',
            field=models.ForeignKey(to='dashboard_app.Test'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='imagecharttest',
            unique_together=set([('image_chart_filter', 'test')]),
        ),
        migrations.AddField(
            model_name='imagechartfilter',
            name='filter',
            field=models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, to='dashboard_app.TestRunFilter', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='imagechartfilter',
            name='image_chart',
            field=models.ForeignKey(to='dashboard_app.ImageReportChart'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='image',
            name='filter',
            field=models.ForeignKey(related_name=b'+', to='dashboard_app.TestRunFilter', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='bundle',
            name='bundle_stream',
            field=models.ForeignKey(related_name=b'bundles', verbose_name='Stream', to='dashboard_app.BundleStream'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='bundle',
            name='uploaded_by',
            field=models.ForeignKey(related_name=b'uploaded_bundles', blank=True, to=settings.AUTH_USER_MODEL, help_text='The user who submitted this bundle', null=True, verbose_name='Uploaded by'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='buglink',
            name='test_result',
            field=models.ManyToManyField(related_name=b'bug_links', to='dashboard_app.TestResult', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='buglink',
            name='test_runs',
            field=models.ManyToManyField(related_name=b'bug_links', to='dashboard_app.TestRun', blank=True),
            preserve_default=True,
        ),
    ]
