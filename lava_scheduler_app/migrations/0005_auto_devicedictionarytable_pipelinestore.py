# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('lava_scheduler_app', '0004_add_pipeline_marks'),
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
        migrations.AlterField(
            model_name='device',
            name='is_pipeline',
            field=models.BooleanField(default=False, verbose_name=b'Pipeline device?'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='testjob',
            name='is_pipeline',
            field=models.BooleanField(default=False, verbose_name=b'Pipeline job?', editable=False),
            preserve_default=True,
        ),
    ]
