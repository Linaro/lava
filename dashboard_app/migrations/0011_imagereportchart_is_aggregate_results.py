# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard_app', '0010_auto_20150116_1533'),
    ]

    operations = [
        migrations.AddField(
            model_name='imagereportchart',
            name='is_aggregate_results',
            field=models.BooleanField(default=False, verbose_name=b'Aggregate parametrized results'),
            preserve_default=True,
        ),
    ]
