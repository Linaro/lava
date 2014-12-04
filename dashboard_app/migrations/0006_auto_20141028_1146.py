# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard_app', '0005_imagereportchart_chart_height'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='imagechartuser',
            name='toggle_percentage',
        ),
        migrations.AddField(
            model_name='imagereportchart',
            name='is_percentage',
            field=models.BooleanField(default=False, verbose_name=b'Percentage'),
            preserve_default=True,
        ),
    ]
