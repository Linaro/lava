# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('lava_results_app', '0003_auto_20150908_1522'),
    ]

    operations = [
        migrations.AlterField(
            model_name='querycondition',
            name='operator',
            field=models.CharField(default=b'exact', max_length=20, verbose_name='Operator', choices=[(b'exact', 'Exact match'), (b'iexact', 'Case-insensitive match'), (b'icontains', 'Contains'), (b'gt', 'Greater than'), (b'lt', 'Less than')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='querycondition',
            name='value',
            field=models.CharField(max_length=40, verbose_name=b'Field value'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='testcase',
            name='suite',
            field=models.ForeignKey(to='lava_results_app.TestSuite'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='testdata',
            name='testjob',
            field=models.ForeignKey(to='lava_scheduler_app.TestJob'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='testsuite',
            name='job',
            field=models.ForeignKey(to='lava_scheduler_app.TestJob'),
            preserve_default=True,
        ),
    ]
