# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('lava_scheduler_app', '0003_populate_master_node'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeviceDictionaryTable',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('kee', models.CharField(max_length=255)),
                ('value', models.TextField()),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='PipelineStore',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('kee', models.CharField(max_length=255)),
                ('value', models.TextField()),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
