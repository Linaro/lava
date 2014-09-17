# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sites', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Analytic',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('analytics_code', models.CharField(max_length=100, blank=True)),
                ('site', models.ForeignKey(to='sites.Site', unique=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
