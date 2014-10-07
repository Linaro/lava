# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard_app', '0003_auto_20140926_1208'),
    ]

    operations = [
        migrations.AddField(
            model_name='imagereportchart',
            name='is_delta',
            field=models.BooleanField(default=False, verbose_name=b'Delta reporting'),
            preserve_default=True,
        ),
    ]
