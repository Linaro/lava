# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('lava_scheduler_app', '0003_populate_master_node'),
    ]

    operations = [
        migrations.AddField(
            model_name='device',
            name='is_pipeline',
            field=models.BooleanField(default=False, verbose_name=b'Is it reserved for the pipeline dispatcher?'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='testjob',
            name='is_pipeline',
            field=models.BooleanField(default=False, verbose_name=b'Is it a pipeline job?'),
            preserve_default=True,
        ),
    ]
