# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard_app', '0006_auto_20141028_1146'),
    ]

    operations = [
        migrations.AddField(
            model_name='imagereportchart',
            name='chart_visibility',
            field=models.CharField(default=b'chart', max_length=20, verbose_name=b'Chart visibility', choices=[(b'chart', b'Chart only'), (b'table', b'Result table only'), (b'both', b'Both')]),
            preserve_default=True,
        ),
    ]
