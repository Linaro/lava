# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard_app', '0009_auto_20150108_0711'),
    ]

    operations = [
        migrations.AddField(
            model_name='imagereportchart',
            name='is_build_number',
            field=models.BooleanField(default=False, verbose_name=b'Use build number'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='imagereportchart',
            name='xaxis_attribute',
            field=models.CharField(max_length=20, null=True, verbose_name=b'X-axis attribute', blank=True),
            preserve_default=True,
        ),
    ]
