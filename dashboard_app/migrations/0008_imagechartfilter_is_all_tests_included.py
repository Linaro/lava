# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard_app', '0007_imagereportchart_chart_visibility'),
    ]

    operations = [
        migrations.AddField(
            model_name='imagechartfilter',
            name='is_all_tests_included',
            field=models.BooleanField(default=False, verbose_name=b'Include all tests from this filter'),
            preserve_default=True,
        ),
    ]
