# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard_app', '0016_auto_20150325_1235'),
    ]

    operations = [
        migrations.AddField(
            model_name='namedattribute',
            name='is_manual',
            field=models.NullBooleanField(),
            preserve_default=True,
        ),
    ]
