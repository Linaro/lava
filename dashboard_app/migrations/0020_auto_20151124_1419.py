# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard_app', '0019_auto_20150702_1529'),
    ]

    operations = [
        migrations.AddField(
            model_name='imagereport',
            name='is_archived',
            field=models.BooleanField(default=False, verbose_name=b'Archived'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='imagereport',
            name='group',
            field=models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, default=None, blank=True, to='auth.Group', null=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='imagereport',
            name='image_report_group',
            field=models.ForeignKey(default=None, blank=True, to='dashboard_app.ImageReportGroup', null=True),
            preserve_default=True,
        ),
    ]
