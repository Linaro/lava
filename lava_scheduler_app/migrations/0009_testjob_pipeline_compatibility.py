# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('lava_scheduler_app', '0008_auto_20151014_1044'),
    ]

    operations = [
        migrations.AddField(
            model_name='testjob',
            name='pipeline_compatibility',
            field=models.IntegerField(default=0, editable=False),
            preserve_default=True,
        ),
    ]
