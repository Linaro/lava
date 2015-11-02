# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0001_initial'),
        ('lava_scheduler_app', '0007_devicetype_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='testjob',
            name='viewing_groups',
            field=models.ManyToManyField(related_name='viewing_groups', default=None, to='auth.Group', blank=True, help_text='Adding groups to an intersection of groups reduces visibility.Adding groups to a union of groups expands visibility.', null=True, verbose_name='Viewing groups'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='testjob',
            name='visibility',
            field=models.IntegerField(default=0, help_text='Visibility affects the TestJob and all results arising from that job, including Queries and Reports.', verbose_name='Visibility type', choices=[(0, b'Publicly visible'), (1, b'Personal only'), (2, b'Group only')]),
            preserve_default=True,
        ),
    ]
