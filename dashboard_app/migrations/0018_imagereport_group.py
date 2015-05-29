# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0001_initial'),
        ('dashboard_app', '0017_namedattribute_is_manual'),
    ]

    operations = [
        migrations.AddField(
            model_name='imagereport',
            name='group',
            field=models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, default=None, to='auth.Group', null=True),
            preserve_default=True,
        ),
    ]
