# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard_app', '0012_auto_20150126_1644'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='imagereportchart',
            name='is_delta',
        ),
        migrations.AddField(
            model_name='imagechartuser',
            name='is_delta',
            field=models.BooleanField(default=False, verbose_name=b'Delta reporting'),
            preserve_default=True,
        ),
    ]
