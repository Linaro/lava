# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard_app', '0004_imagereportchart_is_delta'),
    ]

    operations = [
        migrations.AddField(
            model_name='imagereportchart',
            name='chart_height',
            field=models.PositiveIntegerField(default=200, verbose_name=b'Chart height', validators=[django.core.validators.MinValueValidator(200), django.core.validators.MaxValueValidator(400)]),
            preserve_default=True,
        ),
    ]
