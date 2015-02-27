# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard_app', '0013_auto_20150127_1341'),
    ]

    operations = [
        migrations.AlterField(
            model_name='imagereportchart',
            name='chart_height',
            field=models.PositiveIntegerField(default=300, verbose_name=b'Chart height', validators=[django.core.validators.MinValueValidator(200), django.core.validators.MaxValueValidator(400)]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='imagereportchart',
            name='is_aggregate_results',
            field=models.BooleanField(default=True, verbose_name=b'Aggregate parametrized results'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='imagereportchart',
            name='is_build_number',
            field=models.BooleanField(default=True, verbose_name=b'Use build number'),
            preserve_default=True,
        ),
    ]
