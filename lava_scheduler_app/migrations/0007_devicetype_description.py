# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('lava_scheduler_app', '0006_auto_20150619_1035'),
    ]

    operations = [
        migrations.AddField(
            model_name='devicetype',
            name='description',
            field=models.TextField(default=None, max_length=200, null=True, verbose_name='Device Type Description', blank=True),
            preserve_default=True,
        ),
    ]
