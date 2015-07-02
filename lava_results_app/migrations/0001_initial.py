# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('lava_scheduler_app', '0005_auto_devicedictionarytable_pipelinestore'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActionData',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('action_name', models.CharField(max_length=100)),
                ('action_level', models.CharField(max_length=32)),
                ('action_summary', models.CharField(max_length=100)),
                ('action_description', models.CharField(max_length=200)),
                ('yaml_line', models.PositiveIntegerField(null=True, blank=True)),
                ('description_line', models.PositiveIntegerField(null=True, blank=True)),
                ('log_section', models.CharField(max_length=50, null=True, blank=True)),
                ('duration', models.DecimalField(null=True, max_digits=8, decimal_places=2, blank=True)),
                ('timeout', models.PositiveIntegerField(null=True, blank=True)),
                ('count', models.PositiveIntegerField(null=True, blank=True)),
                ('max_retries', models.PositiveIntegerField(null=True, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='MetaType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=32)),
                ('metatype', models.PositiveIntegerField(help_text='metadata action type', verbose_name='Type', choices=[(0, 'deploy'), (1, 'boot'), (2, 'test'), (3, 'diagnostic'), (4, 'finalize'), (5, 'unknown type')])),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TestCase',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.TextField(help_text='Maximum length: 100 characters', verbose_name='Name', blank=True)),
                ('units', models.TextField(help_text='Units in which measurement value should be\n                     interpreted, for example <q>ms</q>, <q>MB/s</q> etc.\n                     There is no semantic meaning inferred from the value of\n                     this field, free form text is allowed. <br/>Maximum length: 100 characters', verbose_name='Units', blank=True)),
                ('result', models.PositiveSmallIntegerField(help_text='Result classification to pass/fail group', verbose_name='Result', choices=[(0, 'Test passed'), (1, 'Test failed'), (2, 'Test skipped'), (3, 'Unknown outcome')])),
                ('measurement', models.CharField(help_text='Arbitrary value that was measured as a part of this test.', max_length=512, null=True, verbose_name='Measurement', blank=True)),
                ('metadata', models.CharField(help_text='Metadata collected by the pipeline action, stored as YAML.', max_length=1024, null=True, verbose_name='Action meta data as a YAML string', blank=True)),
                ('logged', models.DateTimeField(auto_now=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TestData',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('testjob', models.ForeignKey(related_name='test_data', to='lava_scheduler_app.TestJob')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TestSet',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('name', models.CharField(default=None, max_length=200, null=True, verbose_name='Suite name', blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TestSuite',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(default=None, max_length=200, null=True, verbose_name='Suite name', blank=True)),
                ('job', models.ForeignKey(related_name='test_suites', to='lava_scheduler_app.TestJob')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='testset',
            name='suite',
            field=models.ForeignKey(related_name='test_sets', to='lava_results_app.TestSuite'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='testcase',
            name='suite',
            field=models.ForeignKey(related_name='test_cases', to='lava_results_app.TestSuite'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='testcase',
            name='test_set',
            field=models.ForeignKey(related_name='test_cases', default=None, blank=True, to='lava_results_app.TestSet', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='actiondata',
            name='meta_type',
            field=models.ForeignKey(related_name='actionlevels', to='lava_results_app.MetaType'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='actiondata',
            name='testcase',
            field=models.ForeignKey(related_name='actionlevels', blank=True, to='lava_results_app.TestCase', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='actiondata',
            name='testdata',
            field=models.ForeignKey(related_name='actionlevels', blank=True, to='lava_results_app.TestData', null=True),
            preserve_default=True,
        ),
    ]
