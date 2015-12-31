# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
from django.conf import settings
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('lava_results_app', '0005_auto_20151124_1419'),
    ]

    operations = [
        migrations.CreateModel(
            name='Chart',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.SlugField(unique=True, max_length=1024)),
                ('description', models.TextField(null=True, blank=True)),
                ('is_published', models.BooleanField(default=False, verbose_name=b'Published')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ChartGroup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.SlugField(unique=True, max_length=1024)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ChartQuery',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('chart_type', models.CharField(default=b'pass/fail', max_length=20, verbose_name=b'Chart type', choices=[(b'pass/fail', b'Pass/Fail'), (b'measurement', b'Measurement'), (b'attributes', b'Attributes')])),
                ('target_goal', models.DecimalField(null=True, verbose_name=b'Target goal', max_digits=10, decimal_places=5, blank=True)),
                ('chart_height', models.PositiveIntegerField(default=300, verbose_name=b'Chart height', validators=[django.core.validators.MinValueValidator(200), django.core.validators.MaxValueValidator(400)])),
                ('is_percentage', models.BooleanField(default=False, verbose_name=b'Percentage')),
                ('chart_visibility', models.CharField(default=b'chart', max_length=20, verbose_name=b'Chart visibility', choices=[(b'chart', b'Chart only'), (b'table', b'Result table only'), (b'both', b'Both')])),
                ('xaxis_attribute', models.CharField(max_length=20, null=True, verbose_name=b'X-axis attribute', blank=True)),
                ('representation', models.CharField(default=b'lines', max_length=20, verbose_name=b'Representation', choices=[(b'lines', b'Lines'), (b'bars', b'Bars')])),
                ('relative_index', models.PositiveIntegerField(default=0, verbose_name=b'Order in the chart')),
                ('attributes', models.CharField(max_length=200, null=True, verbose_name=b'Chart attributes', blank=True)),
                ('chart', models.ForeignKey(to='lava_results_app.Chart')),
                ('query', models.ForeignKey(to='lava_results_app.Query')),
            ],
            options={
                'ordering': ['relative_index'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ChartQueryUser',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('start_date', models.CharField(max_length=20)),
                ('is_legend_visible', models.BooleanField(default=True, verbose_name=b'Toggle legend')),
                ('is_delta', models.BooleanField(default=False, verbose_name=b'Delta reporting')),
                ('chart_query', models.ForeignKey(to='lava_results_app.ChartQuery')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='chartqueryuser',
            unique_together=set([('chart_query', 'user')]),
        ),
        migrations.AddField(
            model_name='chart',
            name='chart_group',
            field=models.ForeignKey(default=None, to='lava_results_app.ChartGroup', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='chart',
            name='group',
            field=models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, default=None, to='auth.Group', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='chart',
            name='owner',
            field=models.ForeignKey(default=None, to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='chart',
            name='queries',
            field=models.ManyToManyField(to='lava_results_app.Query', through='lava_results_app.ChartQuery', blank=True),
            preserve_default=True,
        ),
    ]
