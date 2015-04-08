# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard_app', '0015_remove_stale_content_types'),
    ]

    operations = [
        migrations.AlterField(
            model_name='testrunfiltertest',
            name='test',
            field=models.ForeignKey(related_name='testrunfilters', to='dashboard_app.Test'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='testrunfiltertestcase',
            name='test_case',
            field=models.ForeignKey(related_name='testrunfilters', to='dashboard_app.TestCase'),
            preserve_default=True,
        ),
    ]
