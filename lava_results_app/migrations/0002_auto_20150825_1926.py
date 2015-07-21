# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0001_initial'),
        ('lava_results_app', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Query',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.SlugField(help_text=b'The <b>name</b> of a query is used to refer to it in the web UI.', max_length=1024)),
                ('description', models.TextField(null=True, blank=True)),
                ('is_published', models.BooleanField(default=False, verbose_name=b'Published')),
                ('group_by_attribute', models.CharField(max_length=20, null=True, verbose_name=b'group by attribute', blank=True)),
                ('target_goal', models.DecimalField(null=True, verbose_name=b'Target goal', max_digits=10, decimal_places=5, blank=True)),
                ('content_type', models.ForeignKey(verbose_name=b'Query object set', to='contenttypes.ContentType')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, default=None, to='auth.Group', null=True)),
                ('owner', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='QueryCondition',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('field', models.CharField(max_length=50, verbose_name=b'Field name')),
                ('operator', models.CharField(max_length=20, verbose_name='Operator', choices=[('exact', 'Exact match'), ('iexact', 'Case-insensitive match'), ('icontains', 'Contains'), ('gt', 'Greater than'), ('lt', 'Less than')])),
                ('value', models.CharField(max_length=50, verbose_name=b'Field value')),
                ('query', models.ForeignKey(to='lava_results_app.Query')),
                ('table', models.ForeignKey(verbose_name=b'Condition model', to='contenttypes.ContentType')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='QueryGroup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.SlugField(unique=True, max_length=1024)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='query',
            name='query_group',
            field=models.ForeignKey(default=None, to='lava_results_app.QueryGroup', null=True),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='query',
            unique_together=set([('owner', 'name')]),
        ),
    ]
