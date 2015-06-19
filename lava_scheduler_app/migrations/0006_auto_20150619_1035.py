# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('lava_scheduler_app', '0005_auto_devicedictionarytable_pipelinestore'),
    ]

    operations = [
        migrations.CreateModel(
            name='Architecture',
            fields=[
                ('name', models.CharField(help_text='e.g. ARMv7', max_length=100, serialize=False, verbose_name='Architecture version', primary_key=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='BitWidth',
            fields=[
                ('width', models.PositiveSmallIntegerField(help_text='integer: e.g. 32 or 64', serialize=False, verbose_name='Processor bit width', primary_key=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Core',
            fields=[
                ('name', models.CharField(help_text='Name of a specific CPU core, e.g. Cortex-A9', max_length=100, serialize=False, verbose_name='CPU core', primary_key=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ProcessorFamily',
            fields=[
                ('name', models.CharField(help_text='e.g. OMAP4, Exynos', max_length=100, serialize=False, verbose_name='Processor Family', primary_key=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='devicetype',
            name='architecture',
            field=models.ForeignKey(related_name='device_types', blank=True, to='lava_scheduler_app.Architecture', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='devicetype',
            name='bits',
            field=models.ForeignKey(related_name='device_types', blank=True, to='lava_scheduler_app.BitWidth', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='devicetype',
            name='core_count',
            field=models.PositiveSmallIntegerField(help_text='Must be an equal number of each type(s) of core(s).', null=True, verbose_name='Total number of cores', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='devicetype',
            name='cores',
            field=models.ManyToManyField(related_name='device_types', null=True, to='lava_scheduler_app.Core', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='devicetype',
            name='cpu_model',
            field=models.CharField(help_text='e.g. a list of CPU model descriptive strings: OMAP4430 / OMAP4460', max_length=100, null=True, verbose_name='CPU model', blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='devicetype',
            name='processor',
            field=models.ForeignKey(related_name='device_types', blank=True, to='lava_scheduler_app.ProcessorFamily', null=True),
            preserve_default=True,
        ),
    ]
