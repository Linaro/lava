# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('lava_scheduler_app', '0009_testjob_pipeline_compatibility'),
    ]

    operations = [
        migrations.AlterField(
            model_name='device',
            name='current_job',
            field=models.OneToOneField(related_name='+', null=True, on_delete=django.db.models.deletion.SET_NULL, blank=True, to='lava_scheduler_app.TestJob'),
        ),
        migrations.AlterField(
            model_name='device',
            name='last_health_report_job',
            field=models.OneToOneField(related_name='+', null=True, on_delete=django.db.models.deletion.SET_NULL, blank=True, to='lava_scheduler_app.TestJob'),
        ),
        migrations.AlterField(
            model_name='device',
            name='physical_group',
            field=models.ForeignKey(related_name='physicalgroup', default=None, blank=True, to='auth.Group', null=True, verbose_name='Group with physical access'),
        ),
        migrations.AlterField(
            model_name='device',
            name='physical_owner',
            field=models.ForeignKey(related_name='physicalowner', default=None, blank=True, to=settings.AUTH_USER_MODEL, null=True, verbose_name='User with physical access'),
        ),
        migrations.AlterField(
            model_name='devicetype',
            name='cores',
            field=models.ManyToManyField(related_name='device_types', to='lava_scheduler_app.Core', blank=True),
        ),
        migrations.AlterField(
            model_name='testjob',
            name='viewing_groups',
            field=models.ManyToManyField(related_name='viewing_groups', default=None, to='auth.Group', blank=True, help_text='Adding groups to an intersection of groups reduces visibility.Adding groups to a union of groups expands visibility.', verbose_name='Viewing groups'),
        ),
    ]
