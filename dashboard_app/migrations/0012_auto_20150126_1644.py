# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard_app', '0011_imagereportchart_is_aggregate_results'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='imagereportchart',
            options={'ordering': ['relative_index']},
        ),
        migrations.AddField(
            model_name='imagereportchart',
            name='relative_index',
            field=models.PositiveIntegerField(default=0, verbose_name=b'Order in the report'),
            preserve_default=True,
        ),
    ]
